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
- Direkter Einstieg: Verzichte zwingend auf einleitende Formulierungen wie „Das Foto zeigt…", „Die Illustration stellt dar…", „Auf dem Bild ist zu sehen…" oder ähnliche Phrasen.
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
Rolle: Du bist ein KI-Assistent für präzises Lektorat.
Aufgabe: Erstelle eine rein inhaltliche Zusammenfassung des folgenden Textes.
WICHTIGE ANWEISUNG: Beginne deine Antwort direkt mit dem ersten Wort der Zusammenfassung. Formuliere absolut keine Einleitungssätze wie "Hier ist die Zusammenfassung" oder ähnliches.

Kontext: Der Text kann ein Roman, hohe Literatur oder ein Sachbuch sein.

Anleitung:
1. Analysiere den Text.
2. Erfasse bei fiktionalen Texten die Figuren/Schauplätze; bei Sachtexten das Kernthema/die Argumente.
3. Skizziere den Inhalt chronologisch oder gemäß der Gliederung.
4. Verfasse eine sachliche, strukturierte Inhaltsangabe.

Ausgabeformat: Reiner Fließtext, maximal 6.000 Zeichen.
"""

# Schritt 2: Regieleitlinie und Top-3-Stimmen
GUIDELINE_PROMPT_WITH_MATCHING = """
Basierend auf der folgenden Text-Zusammenfassung, erstelle eine prägnante, konsistente Regieleitlinie und wähle die drei passendsten Stimmen aus der bereitgestellten Liste.

**Zusammenfassung des Textes:**
---
{summary}
---

**SEHR WICHTIGE REGELN:**
1.  Analysiere die Liste der verfügbaren Stimmen. Wenn Beschreibungen vorhanden sind, nutze sie. Wenn nur Namen vorhanden sind, schließe aus dem Namen auf den Charakter der Stimme.
2.  Wähle die DREI passendsten Stimmen aus.
3.  Der Name, den du zurückgibst, muss **EXAKT UND ZEICHENGENAU** mit einem Namen aus der Liste übereinstimmen.

**Verfügbare ElevenLabs-Stimmen (können Beschreibungen enthalten oder auch nicht):**
---
{voices_with_descriptions}
---

**Deine Aufgaben:**
1.  Definiere eine GRUNDSTIMMUNG.
2.  Definiere ein SPRECHTEMPO.
3.  Wähle unter Einhaltung der Regeln die Top 3 passendsten Stimmen aus und liste sie auf.

Gib das Ergebnis ausschließlich in diesem Format zurück, jeder Punkt in einer neuen Zeile:
GRUNDSTIMMUNG: [Deine Analyse hier]
SPRECHTEMPO: [Deine Analyse hier]
TOP_STIMME_1: [Exakter Name der besten Stimme aus der Liste]
TOP_STIMME_2: [Exakter Name der zweitbesten Stimme aus der Liste]
TOP_STIMME_3: [Exakter Name der drittbesten Stimme aus der Liste]
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

SCENE_ANALYSIS_PROMPT = """
Rolle: Du bist ein erfahrener Dramaturg und Lektor.
Aufgabe: Analysiere den folgenden Text und zerlege ihn in logische, inhaltliche Szenen. Identifiziere für jede Szene den Inhalt, den Typ und die Stimmung.

Kontext: Der Text kann ein Roman, eine Kurzgeschichte oder ein Sachbuch sein. Eine "Szene" ist ein in sich geschlossener Abschnitt, der durch einen Orts-, Zeit- oder Stimmungswechsel von der nächsten Szene getrennt ist.

Anleitung:
1.  Lies den gesamten Text.
2.  Identifiziere die einzelnen Szenen in chronologischer Reihenfolge.
3.  Bestimme für jede Szene:
    - `scene_content`: Eine sehr kurze Zusammenfassung dessen, was in der Szene passiert (1-2 Sätze).
    - `scene_type`: Der Typ der Szene. Wähle aus: 'Action', 'Dialog', 'Reflexion', 'Beschreibung', 'Exposition'.
    - `scene_mood`: Die vorherrschende Stimmung in der Szene. Wähle aus: 'Spannend', 'Ruhig', 'Melancholisch', 'Neutral', 'Fröhlich', 'Dramatisch', 'Wütend'.
4.  Fasse die allgemeine Grundstimmung des gesamten Textes zusammen.

Ausgabeformat: Gib das Ergebnis AUSSCHLIESSLICH als valides JSON-Objekt zurück. Verwende keine einleitenden Sätze.

Beispiel für das JSON-Format:
{{
  "overall_mood": "Melancholisch mit einem Hoffnungsschimmer",
  "scenes": [
    {{
      "scene_number": 1,
      "scene_content": "Elias und sein Hund Buster durchstreifen eine verlassene Stadt auf der Suche nach Vorräten.",
      "scene_type": "Beschreibung",
      "scene_mood": "Melancholisch"
    }},
    {{
      "scene_number": 2,
      "scene_content": "Ein plötzliches Grollen und eine unerklärliche Finsternis brechen über die Stadt herein.",
      "scene_type": "Action",
      "scene_mood": "Spannend"
    }}
  ]
}}
"""

# Neue Prompts für die Manuskript-Übersetzung
TRANSLATION_GUIDE_PROMPT = """
Analysiere das folgende, vollständige Manuskript und erstelle ein einziges, valides JSON-Objekt.
Das JSON-Objekt muss zwei Schlüssel enthalten: 'style_guide' und 'key_terms'.

**Deutsche Originaltext:**
---
{full_text}
---

**Ausgabeformat (JSON):**
{{
  "style_guide": {{
    "genre_audience": "Eine kurze Analyse des Genres (z.B. 'Postapokalypse', 'Coming-of-Age') und der wahrscheinlichen Zielgruppe",
    "tone_mood": "Beschreibe den Ton (z.B. düster, hoffnungsvoll) und die Stimmung des Textes",
    "narrative_perspective": "Identifiziere die Erzählperspektive (z.B. 'dritte Person, personal')",
    "character_names": "Liste die Hauptcharaktere auf (z.B. Elias, Buster) und deren konsistente Benennung",
    "key_concepts": "Führe zentrale Begriffe der Geschichte auf (z.B. 'Das Große Vergehen', 'Geisterstadt')",
    "stylistic_features": "Beschreibe auffällige sprachliche Stilmittel (z.B. Metaphern, Satzbau, einfache, direkte Sprache)"
  }},
  "key_terms": {{
    "deutscher_begriff_1": "englische_übersetzung_1",
    "deutscher_begriff_2": "englische_übersetzung_2"
  }}
}}

**WICHTIGE REGELN:**
- Antworte AUSSCHLIESSLICH mit dem JSON-Objekt
- Füge keine Erklärungen oder Markdown-Formatierungen wie ```json hinzu
- Das JSON muss valide sein und die beiden Hauptschlüssel enthalten
- Das Glossar soll Eigennamen und Schlüsselkonzepte aus dem Text extrahieren
"""

TRANSLATE_CHUNK_PROMPT = """
Du bist ein professioneller Literaturübersetzer.
Deine Aufgabe ist es, einen deutschen Textabschnitt ins Englische zu übersetzen, wobei du strikt den vorgegebenen "Style & Glossar"-Leitfaden befolgst.

**WICHTIGE REGELN:**
1. Übersetze den Text wortgetreu, aber idiomatisch korrekt
2. Halte dich STRIKT an das vorgegebene Glossar (key_terms) - verwende NUR die dort angegebenen Übersetzungen
3. Bewahre den ursprünglichen Ton und Stil basierend auf dem Style-Guide
4. Stelle sicher, dass Übergänge zum vorherigen englischen Abschnitt flüssig sind
5. Gib AUSSCHLIESSLICH die englische Übersetzung zurück, ohne zusätzliche Kommentare oder Formatierung

**STYLE-GUIDE (strikt befolgen):**
Genre & Zielgruppe: {genre_audience}
Ton & Stimmung: {tone_mood}
Erzählperspektive: {narrative_perspective}
Charakternamen: {character_names}
Schlüsselkonzepte: {key_concepts}
Stilistische Merkmale: {stylistic_features}

**GLOSSAR (key_terms) - VERWENDE NUR DIESE ÜBERSETZUNGEN:**
{key_terms_formatted}

**Deutscher Textabschnitt:**
---
{german_chunk}
---

**Vorheriger englischer Abschnitt (für Übergang):**
---
{previous_english_chunk}
---

**Englische Übersetzung (nur der übersetzte Text, keine Kommentare):**
"""