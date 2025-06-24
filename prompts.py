# prompts.py
ACCESSIBILITY_PROMPT_TEMPLATE = """Du bist eine KI, spezialisiert auf die Erstellung barrierefreier Bildbeschreibungen (Alternativtexte und gegebenenfalls erweiterte Beschreibungen) für E-Books. Deine Aufgabe ist es, Bilder für blinde und sehbehinderte Leser zugänglich zu machen, gemäß den WCAG-Richtlinien und den spezifischen Vorgaben unseres Verlags, wie sie dir hier dargelegt werden.
WICHTIGE ANWEISUNG FÜR DEINE ANTWORT: Deine Antwort muss ausschließlich die generierte Bildbeschreibung enthalten. Formuliere keine Einleitungssätze, keine abschließenden Bemerkungen, keine Höflichkeitsfloskeln oder sonstige Erklärungen zu deiner Vorgehensweise – nur der reine Text im vorgegebenen Format.
Buchkontext: $BUCHKONTEXT
Erstelle nun eine Bildbeschreibung unter strikter Beachtung folgender Richtlinien aus unserem Verlagshandout:
Zweck und Zielgruppe:
- Vermittle blinden oder sehbehinderten Menschen präzise, was auf dem Bild zu sehen ist und welche Inhalte es transportiert. Ermögliche einen barrierefreien Zugang.
- Die Beschreibung soll die Funktion des Bildes im jeweiligen $BUCHKONTEXT klarstellen.
Stil und Formulierung:
- Neutral und deskriptiv: Beschreibe objektiv, was visuell wahrnehmbar ist.
- Keine Interpretation: Vermeide persönliche Deutungen oder Wertungen.
- Direkter Einstieg: Verzichte zwingend auf einleitende Formulierungen wie „Das Foto zeigt…“, „Die Illustration stellt dar…“, „Auf dem Bild ist zu sehen…“ oder ähnliche Phrasen.
- Anführungszeichen: Verwende für Anführungszeichen ausschließlich französische Guillemets («Beispiel»).
- Sprache: Klar, präzise und allgemein verständlich.
Inhalt und Struktur:
- Vom Allgemeinen zum Speziellen: Beginne mit einer allgemeinen Erfassung und gehe dann auf Details ein.
- Wesentliche Elemente: Identifiziere und beschreibe alle relevanten Elemente.
- Bildtyp berücksichtigen: Gib ggf. den Bildtyp an.
- Bei Karten, Tabellen und Diagrammen: Erkläre die dargestellten Daten und deren Beziehungen.
- Relevanz und Redundanzvermeidung: Konzentriere dich auf die Informationen, die für das Verständnis im $BUCHKONTEXT notwendig sind.
Länge:
- So knapp wie möglich, aber so ausführlich wie nötig. Für einfache Bilder kann eine kurze Beschreibung (ca. 140 Zeichen) genügen. Komplexere Bilder erfordern eine ausführlichere Beschreibung.
Atmosphäre/Stimmung (falls relevant): Beschreibe diese kurz, wenn sie für das Verständnis wichtig ist.

FINALES AUSGABEFORMAT:
Basierend auf allen oben genannten Richtlinien, generiere jetzt bitte ZWEI Beschreibungen für das bereitgestellte Bild in genau dem folgenden Format, ohne zusätzliche Einleitungen oder Kommentare:

KURZBESCHREIBUNG (max. 140 Zeichen): [Hier die prägnante, eigenständige Kurzbeschreibung einfügen, die die 140-Zeichen-Grenze strikt einhält.]
---
LANGBESCHREIBUNG: [Hier die detaillierte, erweiterte Beschreibung ohne Längenbeschränkung einfügen.]
"""

SEO_PROMPT = """Analysiere das folgende Bild sorgfältig.
Deine Aufgabe ist es, SEO-optimierte HTML-Attribute für dieses Bild zu generieren:
1. Ein 'alt'-Attribut (Alternativtext)
2. Ein 'title'-Attribut
Beachte dabei die aktuellen SEO Best Practices:
- Das 'alt'-Attribut muss das Bild präzise und prägnant beschreiben. Es ist entscheidend für Barrierefreiheit und das Verständnis des Bildinhalts durch Suchmaschinen. Beschreibe Objekte, Personen, Aktionen und ggf. Text im Bild. Vermeide Keyword-Stuffing.
- Das 'title'-Attribut kann zusätzliche kontextbezogene Informationen liefern.
Gib *nur* die beiden Attribute im folgenden Format zurück, ohne zusätzliche Erklärungen oder Formatierungen:
ALT: [Hier der generierte Alt-Text]
TITLE: [Hier der generierte Title-Text]
"""

# Schritt 1: Zusammenfassung des Manuskripts (Genre-agnostisch)
SUMMARY_PROMPT = """
Rolle und Ziel

Du bist ein KI-gestützter Assistent für literarisches Lektorat. Dein Ziel ist es, eine ausführliche, rein
inhaltliche Zusammenfassung des folgenden Textes zu erstellen. Diese dient als Grundlage für weitere Bearbeitungsschritte.

Kontext

Dir liegt ein Manuskript vor. Dies kann ein Werk der literarischen Prosa (Roman, hohe Literatur) oder ein Sachbuch sein.

Schritt-für-Schritt-Anleitung

1. Analysiere den gesamten Text sorgfältig.
2. Bei fiktionalen Texten: Erfasse die zentralen Figuren und Schauplätze.
3. Bei Sachtexten: Erfasse das Kernthema, die Hauptargumente und die Struktur.
4. Skizziere die wesentlichen Inhalts-Stationen chronologisch oder entsprechend der Gliederung des Textes.
5. Verfasse eine sachliche, strukturierte Inhaltsangabe.

Ausgabeformat und Anforderungen

Format: Fließtext
Stil: Sachlich, neutral, nicht werbend
Länge: Maximal 6.000 Zeichen inkl. Leerzeichen
Sprache: Klar, strukturiert, ohne Interpretation oder Wertung
"""

# Schritt 2: Regieleitlinie und Top-3-Stimmen
GUIDELINE_PROMPT_WITH_MATCHING = """
Basierend auf der folgenden Text-Zusammenfassung, erstelle eine prägnante, konsistente Regieleitlinie für eine Hörbuch- oder Audio-Produktion.

**Zusammenfassung des Textes:**
---
{summary}
---

**Regeln für die Auswahl der Stimmen:**
1.  Lies die Beschreibungen der verfügbaren Stimmen sorgfältig durch.
2.  Wähle die DREI Stimmen aus, deren Beschreibung am besten zur Grundstimmung und zum Inhalt des Textes passen.
3.  Die von dir zurückgegebenen Namen müssen **exakt und zeichengenau** mit den Namen aus der Liste übereinstimmen.
4.  Erfinde keine neuen Namen.

**Verfügbare ElevenLabs-Stimmen (Name und Beschreibung):**
---
{voices_with_descriptions}
---

**Deine Aufgaben:**
1.  Definiere eine GRUNDSTIMMUNG (z.B. sachlich-informativ, nachdenklich, spannend).
2.  Definiere ein SPRECHTEMPO (z.B. moderat und klar, ruhig, dynamisch).
3.  Wähle die Top 3 passendsten Stimmen aus der Liste aus.

Gib das Ergebnis ausschließlich in diesem Format zurück, jeder Punkt in einer neuen Zeile:
GRUNDSTIMMUNG: [Deine Analyse hier]
SPRECHTEMPO: [Deine Analyse hier]
TOP_STIMME_1: [Exakter Name der besten Stimme]
TOP_STIMME_2: [Exakter Name der zweitbesten Stimme]
TOP_STIMME_3: [Exakter Name der drittbesten Stimme]
"""

# Schritt 3: SSML-Anreicherung
SSML_PROMPT = """
Du bist ein Experte für die Erstellung von Hörbüchern und beherrschst SSML (Speech Synthesis Markup Language) perfekt.
Deine Aufgabe ist es, den folgenden Text-Abschnitt mit SSML-Tags anzureichern, um ihn für die Sprach-KI natürlicher und fesselnder klingen zu lassen.

**Regeln:**
1.  Der Originaltext darf **auf keinen Fall verändert, umformuliert oder korrigiert** werden. Füge ausschließlich SSML-Tags hinzu.
2.  Halte dich strikt an die vorgegebene **Regieleitlinie**.
3.  Verwende passende SSML-Tags wie `<break time="...s"/>` für Pausen und `<emphasis level="...">` für Betonungen.
4.  Das Ergebnis muss valides SSML sein, das von der ElevenLabs API verarbeitet werden kann.

**Regieleitlinie:**
---
{guideline}
---

**Zu verarbeitender Text-Abschnitt:**
---
{text_chunk}
---

Gib als Antwort **ausschließlich den mit SSML-Tags angereicherten Text** zurück.
"""