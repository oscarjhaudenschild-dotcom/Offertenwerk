"""Load documents and generate the noise corpus for the scaling experiment."""

import json
import os
import random
import re
from pathlib import Path
from typing import Optional, Set, Dict, List, Tuple

Document = Tuple[str, str, str]  # (text, doc_id, doc_type)

# Filler topics deliberately unrelated to the gold-set answers. Noise must not
# restate the facts under test: a shuffled copy of the pricing document still
# contains "CHF 900", so retrieving it would be scored a miss while actually
# supplying the right answer, which makes the hit rate meaningless.
NOISE_TOPICS = [
    ("Archivierung", "Geschäftsunterlagen sind während zehn Jahren aufzubewahren. "
     "Die Aufbewahrung kann elektronisch erfolgen, sofern die Integrität der Daten "
     "gewährleistet ist und die Unterlagen jederzeit lesbar gemacht werden können."),
    ("Handelsregister", "Eintragungen im Handelsregister werden im Schweizerischen "
     "Handelsamtsblatt veröffentlicht. Änderungen der Organe sind unverzüglich "
     "anzumelden. Die Publikation begründet die Wirkung gegenüber Dritten."),
    ("Datenschutz", "Bearbeitende von Personendaten haben die Grundsätze der "
     "Verhältnismässigkeit und Zweckbindung zu beachten. Betroffene Personen haben "
     "ein Auskunftsrecht über die zu ihrer Person bearbeiteten Daten."),
    ("Arbeitsrecht", "Die wöchentliche Höchstarbeitszeit beträgt für Angestellte in "
     "industriellen Betrieben fünfundvierzig Stunden. Überzeitarbeit ist mit einem "
     "Zuschlag zu entschädigen oder durch Freizeit auszugleichen."),
    ("Revision", "Die eingeschränkte Revision umfasst Befragungen, analytische "
     "Prüfungshandlungen und angemessene Detailprüfungen. Der Revisionsbericht wird "
     "der Generalversammlung vorgelegt."),
    ("Fristen", "Die Frist zur Einreichung beginnt am Tag nach der Zustellung. "
     "Fällt der letzte Tag auf einen Samstag, Sonntag oder Feiertag, so endet die "
     "Frist am nächstfolgenden Werktag."),
    ("Betreibung", "Das Betreibungsverfahren beginnt mit dem Betreibungsbegehren. "
     "Der Zahlungsbefehl wird dem Schuldner zugestellt, der innert zehn Tagen "
     "Rechtsvorschlag erheben kann."),
    ("Immobilien", "Der Eigenmietwert wird als Einkommen besteuert. Unterhaltskosten "
     "können entweder pauschal oder effektiv in Abzug gebracht werden, wobei die "
     "Wahl jährlich neu getroffen werden kann."),
]


class CorpusBuilder:
    """Loads source documents and synthesises the irrelevant-document corpus."""

    def __init__(self, corpus_dir: str = "./corpus"):
        self.corpus_dir = corpus_dir
        self.documents: List[Document] = []

    def load_text_file(self, path: str, doc_type: str = "document") -> List[Document]:
        try:
            text = Path(path).read_text(encoding="utf-8").strip()
        except (OSError, UnicodeDecodeError) as exc:
            print(f"  ! could not read {path}: {exc}")
            return []
        if not text:
            print(f"  ! skipping empty file {path}")
            return []
        doc = (text, Path(path).stem, doc_type)
        self.documents.append(doc)
        return [doc]

    def load_directory(self, directory: str, doc_type: str = "document") -> List[Document]:
        if not os.path.isdir(directory):
            return []
        loaded = []
        for file in sorted(Path(directory).glob("*.txt")):
            loaded.extend(self.load_text_file(str(file), doc_type))
        return loaded

    def add_document(self, text: str, doc_id: str, doc_type: str):
        self.documents.append((text, doc_id, doc_type))

    def generate_noise_corpus(
        self, base_corpus: List[Document], count: int, seed: int = 42
    ) -> List[Document]:
        """
        Build `count` irrelevant documents from unrelated regulatory topics.

        Seeded so a run is reproducible. base_corpus is used only to match the
        typical document length, never for its content.
        """
        rng = random.Random(seed)
        target_words = 120
        if base_corpus:
            lengths = [len(text.split()) for text, _, _ in base_corpus]
            target_words = max(40, sum(lengths) // len(lengths))

        noise: List[Document] = []
        for i in range(count):
            topic, body = NOISE_TOPICS[i % len(NOISE_TOPICS)]
            sentences = [s.strip() + "." for s in body.split(".") if s.strip()]
            text_parts = []
            while len(" ".join(text_parts).split()) < target_words:
                text_parts.append(rng.choice(sentences))
            noise.append((
                " ".join(text_parts),
                f"noise_{topic.lower()}_{i:04d}",
                "noise",
            ))
        return noise

    def build_noise(
        self, base_corpus: List[Document], count: int, mode: str = "unrelated",
        seed: int = 42, protected_values: Optional[Set[int]] = None
    ) -> List[Document]:
        """
        Produce the irrelevant-document corpus.

        unrelated  - different topics entirely; the easy case
        confusable - superseded price lists; the case that should break retrieval
        mixed      - half of each, closest to a real document archive
        """
        if mode == "unrelated":
            return self.generate_noise_corpus(base_corpus, count, seed)
        if mode == "confusable":
            return self.generate_confusable_noise(
                base_corpus, count, seed, protected_values)
        if mode == "mixed":
            half = count // 2
            merged = (
                self.generate_noise_corpus(base_corpus, count - half, seed)
                + self.generate_confusable_noise(
                    base_corpus, half, seed, protected_values)
            )
            random.Random(seed).shuffle(merged)
            return merged
        raise ValueError(f"unknown noise mode '{mode}' (use unrelated, confusable or mixed)")

    # Firms and service blocks a distractor may carry. A distractor that keeps
    # its source's firm name and every one of its service blocks is a copy with
    # different numbers, not a separate offer - and "wrong document" stops
    # meaning anything, because the text would have been right.
    NOISE_FIRMS = [
        "Alpina Logistik AG", "Bergsicht Treuhand GmbH", "Cordis Handels AG",
        "Delta Pharma GmbH", "Eiger Immobilien AG", "Fontana Services GmbH",
        "Granit Bau AG", "Helvetia Textil GmbH", "Iris Medizintechnik AG",
        "Juraquell Getränke GmbH", "Kranich Logistik AG", "Lavendel Kosmetik GmbH",
    ]
    NOISE_CONTACTS = [
        "P. Muster", "Q. Muster", "R. Muster", "S. Muster", "T. Muster", "U. Muster",
    ]
    # Headings that open a service block. Dropping some of them shortens the
    # offer the way a smaller mandate would.
    BLOCK_HEADINGS = [
        "Buchhaltung und Mehrwertsteuer", "Personaladministration / Lohnbuchhaltung",
        "Steuererklärung einer juristischen Person", "Gründung", "Domizil",
        "Verwaltungsrat / Zeichnungsberechtigter",
        "Accounting and VAT", "Salary administration / Payroll", "Company taxes",
        "Company establishment", "Authorised signatory", "Domicile address",
    ]

    def generate_confusable_noise(
        self, base_corpus: List[Document], count: int, seed: int = 42,
        protected_values: Optional[Set[int]] = None,
    ) -> List[Document]:
        """
        Build `count` documents that look like the answer documents but state
        different values.

        This models the real hazard in the practitioner's archive: not an unrelated
        document about data protection, but a superseded price list from an
        older offer. Same topic, same wording, wrong numbers - exactly the case
        where the retriever has no lexical signal to prefer the current one.

        Every number is shifted so no noise document can accidentally supply the
        correct answer.
        """
        rng = random.Random(seed)
        contexts = [
            "Tarifblatt {year}", "Ansätze Zweigstelle {city}", "Offerte {year} (abgelaufen)",
            "Preisliste {year}, ersetzt", "Konditionen Mandat {city}",
        ]
        years = ["2016", "2017", "2018", "2019", "2020", "2021"]
        cities = ["Luzern", "Basel", "Chur", "St. Gallen", "Winterthur", "Lugano"]

        # Values no distractor may state, pooled across the whole corpus. A
        # per-document guard only stopped a distractor from reproducing its own
        # source's figures; a distractor derived from one offer could still land
        # on another offer's correct answer by chance, which it did in 6.1% of
        # measurements.
        protected = set(protected_values or ())
        for text, _, _ in base_corpus:
            protected.update(int(n) for n in re.findall(r"\d+", text))

        noise: List[Document] = []
        for i in range(count):
            text, source_id, _ = base_corpus[i % len(base_corpus)]
            header = rng.choice(contexts).format(
                year=rng.choice(years), city=rng.choice(cities)
            )
            body = self._perturb_numbers(text, rng, protected)
            body = self._reassign_party(body, rng)
            body = self._drop_narrative(body)
            body = self._vary_scope(body, rng)
            noise.append((
                f"{header}. {body}",
                f"confusable_{source_id}_{i:04d}",
                "noise_confusable",
            ))
        return noise

    @classmethod
    def _reassign_party(cls, text: str, rng: random.Random) -> str:
        """Give the distractor its own client, not the source's."""
        firm = rng.choice(cls.NOISE_FIRMS)
        contact = rng.choice(cls.NOISE_CONTACTS)
        text = re.sub(r"Muster [A-Z](?:\s+(?:AG|GmbH|Ltd\.?|Consulting|Foundation|Capital))?",
                      firm, text)
        text = re.sub(r"\b[A-Z]\. Beispiel\b", contact, text)
        return text

    @classmethod
    def _drop_narrative(cls, text: str) -> str:
        """
        Remove everything before the first service block.

        A superseded price sheet is a price sheet, not a covering letter: it
        does not repeat why the client approached the firm. Keeping that opening
        made every distractor carry its source's one distinctive passage, so a
        question about that passage could be answered from the distractor.
        """
        lines = text.split("\n")
        first = next((i for i, l in enumerate(lines) if l.strip() in cls.BLOCK_HEADINGS), None)
        if first is None:
            return text
        return "\n".join(lines[:1] + lines[first:])

    @classmethod
    def _vary_scope(cls, text: str, rng: random.Random) -> str:
        """
        Drop roughly a third of the service blocks.

        A smaller mandate covers fewer services. Without this every distractor
        described exactly the same scope as its source, word for word.
        """
        lines = text.split("\n")
        present = [i for i, l in enumerate(lines) if l.strip() in cls.BLOCK_HEADINGS]
        if len(present) < 2:
            return text
        drop = rng.sample(present, max(1, len(present) // 3))
        remove = set()
        for start in drop:
            end = next((p for p in present if p > start), len(lines))
            remove.update(range(start, end))
        return "\n".join(l for i, l in enumerate(lines) if i not in remove)

    @staticmethod
    def _perturb_numbers(text: str, rng: random.Random,
                         protected: Optional[Set[int]] = None) -> str:
        """
        Replace every number with a plausible but different one.

        Magnitude is preserved so the text stays believable: a rate near 250
        becomes another rate near 250, never 3 and never 90000.

        No replacement may equal ANY number appearing in the source document.
        Shifting each number independently is not enough: one value can land on
        another value from the same table, which would hand the correct answer
        back to the retriever and silently inflate the hit rate.
        """
        forbidden = {int(n) for n in re.findall(r"\d+", text)}
        forbidden |= set(protected or ())

        def replace(match: "re.Match") -> str:
            value = int(match.group())
            if value == 0:
                return match.group()
            if value >= 1000:
                steps = [-500, -250, 250, 500, 1000]
            elif value >= 100:
                steps = [-60, -40, -20, 20, 40, 60]
            elif value >= 10:
                steps = [-8, -5, -3, 3, 5, 8]
            else:
                steps = [-3, -2, -1, 1, 2, 3]

            candidates = [value + s for s in steps]
            valid = [c for c in candidates if c > 0 and c not in forbidden]
            if valid:
                return str(rng.choice(valid))
            # Widen the search rather than give up and leak the original.
            offset = 1
            while offset < 10000:
                for c in (value + offset, value - offset):
                    if c > 0 and c not in forbidden:
                        return str(c)
                offset += 1
            return str(value)

        return re.sub(r"\d+", replace, text)

    def get_documents(self) -> List[Document]:
        return self.documents

    def save_manifest(self, path: str = "./corpus/manifest.json"):
        """Record exactly which documents took part, for reproducibility."""
        manifest: Dict = {"document_count": len(self.documents), "by_type": {}, "documents": []}
        for text, doc_id, doc_type in self.documents:
            manifest["by_type"][doc_type] = manifest["by_type"].get(doc_type, 0) + 1
            manifest["documents"].append({
                "doc_id": doc_id,
                "doc_type": doc_type,
                "word_count": len(text.split()),
            })
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)

    @staticmethod
    def create_bootstrap_corpus() -> List[Document]:
        """Small demo corpus so the pipeline can be exercised before real data exists."""
        return [
            ("Die Stundenansätze richten sich nach der Qualifikation der ausführenden Person. "
             "Ein diplomierter Treuhandexperte wird mit CHF 250 pro Stunde verrechnet. "
             "Ein Treuhänder mit eidgenössischem Fachausweis wird mit CHF 160 pro Stunde verrechnet. "
             "Ein Mitarbeiter der Administration wird mit CHF 120 pro Stunde verrechnet.",
             "doc_hourly_rates", "pricing"),
            ("Die Personaladministration wird nach Anzahl Mitarbeitende gestaffelt verrechnet. "
             "Bei einem bis zwei Mitarbeitenden betragen die Kosten CHF 1000 pro Mitarbeiter und Jahr. "
             "Bei drei bis sieben Mitarbeitenden betragen die Kosten CHF 900 pro Mitarbeiter und Jahr. "
             "Bei acht bis fünfzehn Mitarbeitenden betragen die Kosten CHF 800 pro Mitarbeiter und Jahr. "
             "Ab sechzehn Mitarbeitenden betragen die Kosten CHF 700 pro Mitarbeiter und Jahr.",
             "doc_personnel_tiers", "pricing"),
            ("Für die Gründung einer Gesellschaft arbeiten wir mit einem lokalen Notar zusammen. "
             "Der Notar erstellt sämtliche erforderlichen Unterlagen und koordiniert die Gründerversammlung. "
             "Die Kosten für eine Gründung liegen zwischen CHF 2000 und CHF 2500. "
             "Darin enthalten sind die Notargebühren und die Handelsregistergebühren.",
             "doc_formation", "offer"),
            ("Das Obligationenrecht regelt in den Artikeln 957 und folgende die Buchführungspflicht. "
             "Juristische Personen sind zur ordentlichen Buchführung verpflichtet. "
             "Die Bücher sind so zu führen, dass sich die Vermögenslage jederzeit feststellen lässt. "
             "Der Jahresabschluss besteht aus Bilanz, Erfolgsrechnung und Anhang.",
             "doc_or_957", "legal"),
            ("Die Mehrwertsteuerpflicht beginnt bei einem Jahresumsatz von CHF 100000. "
             "Der Normalsatz der Mehrwertsteuer beträgt 8.1 Prozent. "
             "Die Abrechnung erfolgt in der Regel quartalsweise. "
             "Zusätzlich ist jährlich eine Umsatzabstimmung zu erstellen.",
             "doc_mwst", "legal"),
            ("Die laufende Buchführung wird nach effektivem Zeitaufwand abgerechnet. "
             "Als Richtwert werden fünfzig Buchungen pro Stunde angenommen. "
             "Für den Jahresabschluss werden acht Stunden Bearbeitung und zwei Stunden Kontrolle gerechnet. "
             "Die Kontrolle erfolgt nach dem Vier-Augen-Prinzip durch eine zweite Person.",
             "doc_bookkeeping", "pricing"),
        ]
