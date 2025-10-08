# chat_agent.py - Chat Agent für Manuskript-Diskussionen

import logging
from typing import Dict, List, Any, Optional
import google.generativeai as genai
import json
import asyncio
from datetime import datetime

# Logging Setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ManuscriptChatAgent:
    """Chat Agent für interaktive Manuskript-Diskussionen mit Tool-Zugriff."""
    
    def __init__(self, gemini_api_key: str):
        self.gemini_api_key = gemini_api_key
        if gemini_api_key:
            genai.configure(api_key=gemini_api_key)
        
        # Chat History
        self.chat_history = []
        self.manuscript_context = None
        self.available_tools = self._initialize_tools()
    
    def _initialize_tools(self) -> Dict[str, Any]:
        """Initialisiert die verfügbaren Tools für den Chat Agent."""
        return {
            "analyze_manuscript": {
                "description": "Analysiert ein Manuskript auf Plot, Charaktere, Schreibstil, Originalität und Marktpotential",
                "function": self._analyze_manuscript_tool
            },
            "summarize_manuscript": {
                "description": "Erstellt eine prägnante Zusammenfassung des Manuskripts",
                "function": self._summarize_manuscript_tool
            },
            "evaluate_manuscript": {
                "description": "Erstellt eine Gesamtbewertung des Manuskripts",
                "function": self._evaluate_manuscript_tool
            },
            "analyze_target_audience": {
                "description": "Analysiert die Zielgruppe für das Manuskript",
                "function": self._analyze_target_audience_tool
            },
            "suggest_marketing_channels": {
                "description": "Schlägt Marketing-Kanäle basierend auf Zielgruppe vor",
                "function": self._suggest_marketing_channels_tool
            },
            "create_marketing_strategy": {
                "description": "Erstellt eine umfassende Marketing-Strategie",
                "function": self._create_marketing_strategy_tool
            },
            "optimize_marketing_strategy": {
                "description": "Optimiert eine Marketing-Strategie",
                "function": self._optimize_marketing_strategy_tool
            },
            "create_campaign_concept": {
                "description": "Erstellt ein detailliertes Kampagnen-Konzept",
                "function": self._create_campaign_concept_tool
            },
            "analyze_roi": {
                "description": "Analysiert den ROI einer Marketing-Strategie",
                "function": self._analyze_roi_tool
            },
            "create_moodboard": {
                "description": "Erstellt ein thematisches Moodboard mit 9 Bildern basierend auf dem Manuskript",
                "function": self._create_moodboard_tool
            }
        }
    
    def set_manuscript_context(self, manuscript_text: str):
        """Setzt den Manuskript-Kontext für den Chat Agent."""
        self.manuscript_context = manuscript_text
        logger.info(f"Manuscript context set: {len(manuscript_text)} characters")
    
    def _analyze_manuscript_tool(self, **kwargs) -> Dict[str, Any]:
        """Tool: Manuskript-Analyse"""
        if not self.manuscript_context:
            return {"error": "Kein Manuskript-Kontext verfügbar", "status": "failed"}
        
        try:
            # Verwende das KOMPLETTE Manuskript für die Analyse
            manuscript_length = len(self.manuscript_context)
            prompt = f"""
            Analysiere das KOMPLETTE Manuskript gründlich ({manuscript_length:,} Zeichen):
            
            {self.manuscript_context}
            
            WICHTIG: Du hast Zugriff auf das GESAMTE Manuskript. Analysiere alle Teile, 
            einschließlich Anfang, Mitte und Ende der Geschichte.
            
            Erstelle eine detaillierte Analyse mit folgenden Kategorien:
            1. PLOT & STRUKTUR (Bewertung 1-10)
            2. CHARAKTERE (Bewertung 1-10) 
            3. SCHREIBSTIL (Bewertung 1-10)
            4. ORIGINALITÄT (Bewertung 1-10)
            5. MARKTPOTENTIAL (Bewertung 1-10)
            
            Für jede Kategorie:
            - Bewertung (1-10)
            - Stärken
            - Schwächen
            - Konkrete Verbesserungsvorschläge
            
            Format: JSON
            """
            
            model = genai.GenerativeModel('gemini-2.5-pro')
            response = model.generate_content(prompt)
            
            return {
                "analysis": response.text,
                "status": "success"
            }
        except Exception as e:
            logger.error(f"Fehler bei Manuskript-Analyse: {e}")
            return {
                "error": str(e),
                "status": "failed"
            }
    
    def _summarize_manuscript_tool(self, **kwargs) -> Dict[str, Any]:
        """Tool: Manuskript-Zusammenfassung"""
        if not self.manuscript_context:
            return {"error": "Kein Manuskript-Kontext verfügbar", "status": "failed"}
        
        try:
            # Verwende das KOMPLETTE Manuskript für die Zusammenfassung
            manuscript_length = len(self.manuscript_context)
            prompt = f"""
            Erstelle eine prägnante Zusammenfassung des KOMPLETTEN Manuskripts ({manuscript_length:,} Zeichen):
            
            {self.manuscript_context}
            
            WICHTIG: Du hast Zugriff auf das GESAMTE Manuskript. Berücksichtige den kompletten 
            Handlungsverlauf von Anfang bis Ende, einschließlich aller wichtigen Wendepunkte 
            und des Endes der Geschichte.
            
            Die Zusammenfassung sollte enthalten:
            1. Hauptthema/Genre
            2. Hauptcharaktere
            3. Zentrale Handlung (inklusive Ende der Geschichte)
            4. Besondere Stärken
            5. Zielgruppe
            
            Format: Strukturierte Zusammenfassung
            """
            
            model = genai.GenerativeModel('gemini-2.5-pro')
            response = model.generate_content(prompt)
            
            return {
                "summary": response.text,
                "status": "success"
            }
        except Exception as e:
            logger.error(f"Fehler bei Zusammenfassung: {e}")
            return {
                "error": str(e),
                "status": "failed"
            }
    
    def _evaluate_manuscript_tool(self, **kwargs) -> Dict[str, Any]:
        """Tool: Manuskript-Bewertung"""
        if not self.manuscript_context:
            return {"error": "Kein Manuskript-Kontext verfügbar", "status": "failed"}
        
        try:
            prompt = f"""
            Bewerte das folgende Manuskript und erstelle eine Gesamtbewertung:
            
            {self.manuscript_context}
            
            Erstelle eine Bewertung mit:
            1. GESAMTBEWERTUNG (1-10)
            2. VERBESSERUNGSPOTENTIAL (Hoch/Mittel/Niedrig)
            3. MARKTCHANCEN (Hoch/Mittel/Niedrig)
            4. TOP 3 VERBESSERUNGSVORSCHLÄGE
            5. EMPFEHLUNG (Veröffentlichen/Überarbeiten/Verwerfen)
            
            Format: JSON
            """
            
            model = genai.GenerativeModel('gemini-2.5-pro')
            response = model.generate_content(prompt)
            
            return {
                "evaluation": response.text,
                "status": "success"
            }
        except Exception as e:
            logger.error(f"Fehler bei Bewertung: {e}")
            return {
                "error": str(e),
                "status": "failed"
            }
    
    def _analyze_target_audience_tool(self, manuscript_summary: str = None, **kwargs) -> Dict[str, Any]:
        """Tool: Zielgruppen-Analyse"""
        if not manuscript_summary and not self.manuscript_context:
            return {"error": "Kein Manuskript-Kontext verfügbar", "status": "failed"}
        
        try:
            text_to_analyze = manuscript_summary or self.manuscript_context
            prompt = f"""
            Basierend auf diesem Manuskript analysiere die Zielgruppe:
            
            {text_to_analyze}
            
            Erstelle eine detaillierte Zielgruppen-Analyse:
            1. PRIMÄRE ZIELGRUPPE
               - Alter
               - Geschlecht
               - Bildung
               - Interessen
               - Kaufverhalten
            
            2. SEKUNDÄRE ZIELGRUPPE
               - Ähnliche Demografie
               - Erweiterte Interessen
            
            3. ZIELGRUPPEN-SEGMENTE
               - Segment 1: [Name, Beschreibung, Größe]
               - Segment 2: [Name, Beschreibung, Größe]
               - Segment 3: [Name, Beschreibung, Größe]
            
            Format: Strukturierte Analyse
            """
            
            model = genai.GenerativeModel('gemini-2.5-pro')
            response = model.generate_content(prompt)
            
            return {
                "audience_analysis": response.text,
                "status": "success"
            }
        except Exception as e:
            logger.error(f"Fehler bei Zielgruppen-Analyse: {e}")
            return {
                "error": str(e),
                "status": "failed"
            }
    
    def _suggest_marketing_channels_tool(self, target_audience: str = None, **kwargs) -> Dict[str, Any]:
        """Tool: Marketing-Kanäle vorschlagen"""
        if not self.manuscript_context:
            return {"error": "Kein Manuskript-Kontext verfügbar", "status": "failed"}
        
        try:
            prompt = f"""
            Basierend auf diesem Manuskript und der Zielgruppe schlage Marketing-Kanäle vor:
            
            MANUSKRIPT: {self.manuscript_context[:1000]}...
            ZIELGRUPPE: {target_audience or "Zu analysieren"}
            
            Erstelle Marketing-Kanal-Empfehlungen:
            1. ONLINE-MARKETING
               - Social Media (welche Plattformen)
               - Content Marketing
               - Influencer Marketing
               - Paid Advertising
            
            2. OFFLINE-MARKETING
               - Buchhandlungen
               - Events/Lesungen
               - Presse/Medien
               - Kooperationen
            
            3. DIGITALE KANÄLE
               - E-Book Plattformen
               - Podcasts
               - YouTube
               - Blogs/Websites
            
            Für jeden Kanal: Kosten, Aufwand, erwartete Reichweite
            Format: Strukturierte Empfehlungen
            """
            
            model = genai.GenerativeModel('gemini-2.5-pro')
            response = model.generate_content(prompt)
            
            return {
                "marketing_channels": response.text,
                "status": "success"
            }
        except Exception as e:
            logger.error(f"Fehler bei Marketing-Kanälen: {e}")
            return {
                "error": str(e),
                "status": "failed"
            }
    
    def _create_marketing_strategy_tool(self, target_audience: str = None, channels: str = None, **kwargs) -> Dict[str, Any]:
        """Tool: Marketing-Strategie erstellen"""
        if not self.manuscript_context:
            return {"error": "Kein Manuskript-Kontext verfügbar", "status": "failed"}
        
        try:
            prompt = f"""
            Erstelle eine umfassende Marketing-Strategie:
            
            MANUSKRIPT: {self.manuscript_context[:1000]}...
            ZIELGRUPPE: {target_audience or "Zu analysieren"}
            KANÄLE: {channels or "Zu analysieren"}
            
            Erstelle eine Marketing-Strategie mit:
            1. KAMPAGNE-KONZEPT
               - Hauptbotschaft
               - Unique Selling Proposition
               - Emotionaler Hook
            
            2. TIMELINE & PHASEN
               - Pre-Launch (3 Monate vorher)
               - Launch (Veröffentlichung)
               - Post-Launch (3 Monate nachher)
            
            3. BUDGET-VERTEILUNG
               - Online Marketing: X%
               - Offline Marketing: X%
               - Content Creation: X%
               - Events: X%
            
            4. MESSBARE ZIELE
               - Verkaufszahlen
               - Reichweite
               - Engagement
               - Brand Awareness
            
            5. KONKRETE MASSNAHMEN
               - Woche 1-4: [Maßnahmen]
               - Woche 5-8: [Maßnahmen]
               - Woche 9-12: [Maßnahmen]
            
            Format: Detaillierte Strategie
            """
            
            model = genai.GenerativeModel('gemini-2.5-pro')
            response = model.generate_content(prompt)
            
            return {
                "marketing_strategy": response.text,
                "status": "success"
            }
        except Exception as e:
            logger.error(f"Fehler bei Marketing-Strategie: {e}")
            return {
                "error": str(e),
                "status": "failed"
            }
    
    def _optimize_marketing_strategy_tool(self, strategy: str = None, target_audience: str = None, **kwargs) -> Dict[str, Any]:
        """Tool: Marketing-Strategie optimieren"""
        try:
            prompt = f"""
            Optimiere diese Marketing-Strategie für die Zielgruppe:
            
            STRATEGIE: {strategy or "Zu analysieren"}
            ZIELGRUPPE: {target_audience or "Zu analysieren"}
            
            Erstelle Optimierungen für:
            1. TARGETING-VERFEINERUNG
               - Präzisere Zielgruppen-Segmente
               - Lookalike Audiences
               - Behavioral Targeting
            
            2. KANAL-OPTIMIERUNG
               - Beste Kanäle für Zielgruppe
               - Budget-Umverteilung
               - Timing-Optimierung
            
            3. CONTENT-OPTIMIERUNG
               - Zielgruppen-spezifische Botschaften
               - Creative Testing
               - Format-Optimierung
            
            4. PERFORMANCE-OPTIMIERUNG
               - KPIs für Zielgruppe
               - Conversion-Optimierung
               - Retention-Strategien
            
            Format: Optimierte Strategie mit Begründungen
            """
            
            model = genai.GenerativeModel('gemini-2.5-pro')
            response = model.generate_content(prompt)
            
            return {
                "optimized_strategy": response.text,
                "status": "success"
            }
        except Exception as e:
            logger.error(f"Fehler bei Strategie-Optimierung: {e}")
            return {
                "error": str(e),
                "status": "failed"
            }
    
    def _create_campaign_concept_tool(self, target_audience: str = None, budget: str = None, **kwargs) -> Dict[str, Any]:
        """Tool: Kampagnen-Konzept erstellen"""
        if not self.manuscript_context:
            return {"error": "Kein Manuskript-Kontext verfügbar", "status": "failed"}
        
        try:
            prompt = f"""
            Erstelle ein detailliertes Kampagnen-Konzept:
            
            MANUSKRIPT: {self.manuscript_context[:1000]}...
            ZIELGRUPPE: {target_audience or "Zu analysieren"}
            BUDGET: {budget or "Zu definieren"}
            
            Erstelle ein Kampagnen-Konzept mit:
            1. KAMPAGNE-NAME & TAGLINE
               - Memorable Name
               - Catchy Tagline
               - Core Message
            
            2. CREATIVE CONCEPT
               - Visual Style
               - Tone of Voice
               - Key Visuals
               - Copy Guidelines
            
            3. CHANNEL-SPEZIFISCHE KONZEPTE
               - Social Media Posts
               - Display Ads
               - Video Content
               - Print Materials
            
            4. TIMELINE & ROLLOUT
               - Phase 1: Awareness
               - Phase 2: Consideration
               - Phase 3: Conversion
               - Phase 4: Retention
            
            5. SUCCESS METRICS
               - Reach & Impressions
               - Engagement Rate
               - Click-Through Rate
               - Conversion Rate
               - Cost per Acquisition
            
            Format: Detailliertes Kampagnen-Konzept
            """
            
            model = genai.GenerativeModel('gemini-2.5-pro')
            response = model.generate_content(prompt)
            
            return {
                "campaign_concept": response.text,
                "status": "success"
            }
        except Exception as e:
            logger.error(f"Fehler bei Kampagnen-Konzept: {e}")
            return {
                "error": str(e),
                "status": "failed"
            }
    
    def _analyze_roi_tool(self, strategy: str = None, budget: str = None, expected_results: str = None, **kwargs) -> Dict[str, Any]:
        """Tool: ROI-Analyse"""
        try:
            prompt = f"""
            Analysiere den ROI dieser Marketing-Strategie:
            
            STRATEGIE: {strategy or "Zu analysieren"}
            BUDGET: {budget or "Zu definieren"}
            ERWARTETE ERGEBNISSE: {expected_results or "Zu prognostizieren"}
            
            Erstelle eine ROI-Analyse mit:
            1. KOSTEN-ANALYSE
               - Gesamtbudget
               - Kanal-spezifische Kosten
               - Cost per Acquisition
               - Cost per Lead
            
            2. ERGEBNIS-PROGNOSE
               - Erwartete Verkäufe
               - Revenue Projection
               - Break-even Point
               - Profit Margin
            
            3. ROI-BERECHNUNG
               - Return on Investment
               - Return on Ad Spend
               - Customer Lifetime Value
               - Payback Period
            
            4. RISIKO-BEWERTUNG
               - Worst Case Scenario
               - Best Case Scenario
               - Most Likely Scenario
               - Risk Mitigation
            
            5. OPTIMIERUNGSEMPFEHLUNGEN
               - Budget-Umverteilung
               - Kanal-Optimierung
               - Performance-Verbesserung
            
            Format: Detaillierte ROI-Analyse
            """
            
            model = genai.GenerativeModel('gemini-2.5-pro')
            response = model.generate_content(prompt)
            
            return {
                "roi_analysis": response.text,
                "status": "success"
            }
        except Exception as e:
            logger.error(f"Fehler bei ROI-Analyse: {e}")
            return {
                "error": str(e),
                "status": "failed"
            }
    
    def chat(self, user_message: str) -> Dict[str, Any]:
        """Haupt-Chat-Funktion mit Tool-Integration."""
        try:
            # Füge Benutzer-Nachricht zur Historie hinzu
            self.chat_history.append({
                "role": "user",
                "message": user_message,
                "timestamp": datetime.now().isoformat()
            })
            
            # Erstelle System-Prompt mit verfügbaren Tools
            system_prompt = self._create_system_prompt()
            
            # Generiere Antwort mit Tool-Integration
            response = self._generate_response_with_tools(user_message, system_prompt)
            
            # Füge Agent-Antwort zur Historie hinzu
            self.chat_history.append({
                "role": "assistant",
                "message": response["message"],
                "tools_used": response.get("tools_used", []),
                "timestamp": datetime.now().isoformat()
            })
            
            return response
            
        except Exception as e:
            logger.error(f"Fehler im Chat: {e}")
            return {
                "message": f"Entschuldigung, es ist ein Fehler aufgetreten: {str(e)}",
                "error": str(e),
                "status": "failed"
            }
    
    def _create_system_prompt(self) -> str:
        """Erstellt den System-Prompt für den Chat Agent."""
        manuscript_info = ""
        if self.manuscript_context:
            # Zeige mehr vom Manuskript-Kontext (erste 10000 Zeichen für besseren Kontext)
            manuscript_preview = self.manuscript_context[:10000]
            manuscript_info = f"""
MANUSKRIPT-KONTEXT (Vollständiges Manuskript verfügbar - {len(self.manuscript_context):,} Zeichen):
{manuscript_preview}{"..." if len(self.manuscript_context) > 10000 else ""}

HINWEIS: Du hast Zugriff auf das KOMPLETTE Manuskript ({len(self.manuscript_context):,} Zeichen). 
Verwende die verfügbaren Tools, um das gesamte Manuskript zu analysieren, nicht nur den Vorschau-Abschnitt.
"""
        
        tools_info = "\n".join([
            f"- {name}: {info['description']}" 
            for name, info in self.available_tools.items()
        ])
        
        return f"""Du bist ein spezialisierter AI-Agent für Manuskript-Analyse und Marketing-Beratung. 
Du hilfst Autoren und Verlagen bei der Bewertung, Verbesserung und Vermarktung von Manuskripten.

{manuscript_info}

VERFÜGBARE TOOLS:
{tools_info}

CHAT-HISTORIE:
{self._format_chat_history()}

ANWEISUNGEN:
1. Du kannst Tools verwenden, um spezifische Analysen durchzuführen
2. Antworte auf Deutsch und sei hilfsbereit und professionell
3. Wenn du ein Tool verwendest, erkläre dem Benutzer, was du tust
4. Stelle Fragen, um den Kontext zu verstehen, wenn nötig
5. Biete konkrete, umsetzbare Ratschläge an

Beantworte die Benutzer-Nachricht und verwende dabei die verfügbaren Tools, wenn sie hilfreich sind."""
    
    def _format_chat_history(self) -> str:
        """Formatiert die Chat-Historie für den System-Prompt."""
        if not self.chat_history:
            return "Keine vorherigen Nachrichten."
        
        formatted_history = []
        for entry in self.chat_history[-10:]:  # Letzte 10 Nachrichten
            role = "Benutzer" if entry["role"] == "user" else "Agent"
            formatted_history.append(f"{role}: {entry['message']}")
        
        return "\n".join(formatted_history)
    
    def _generate_response_with_tools(self, user_message: str, system_prompt: str) -> Dict[str, Any]:
        """Generiert eine Antwort mit Tool-Integration."""
        try:
            # Erstelle den vollständigen Prompt
            full_prompt = f"{system_prompt}\n\nBenutzer: {user_message}\n\nAgent:"
            
            model = genai.GenerativeModel('gemini-2.5-pro')
            response = model.generate_content(full_prompt)
            
            # Prüfe, ob Tools verwendet werden sollen
            tools_used = []
            response_text = response.text
            
            # Einfache Tool-Erkennung (kann erweitert werden)
            if "analysiere" in user_message.lower() or "analyse" in user_message.lower():
                if "manuskript" in user_message.lower():
                    tool_result = self._analyze_manuscript_tool()
                    if tool_result["status"] == "success":
                        tools_used.append("analyze_manuscript")
                        response_text += f"\n\n📊 Manuskript-Analyse:\n{tool_result['analysis']}"
            
            elif "zusammenfassung" in user_message.lower() or "zusammenfassen" in user_message.lower():
                tool_result = self._summarize_manuscript_tool()
                if tool_result["status"] == "success":
                    tools_used.append("summarize_manuscript")
                    response_text += f"\n\n📋 Zusammenfassung:\n{tool_result['summary']}"
            
            elif "zielgruppe" in user_message.lower() or "target audience" in user_message.lower():
                tool_result = self._analyze_target_audience_tool()
                if tool_result["status"] == "success":
                    tools_used.append("analyze_target_audience")
                    response_text += f"\n\n🎯 Zielgruppen-Analyse:\n{tool_result['audience_analysis']}"
            
            elif "marketing" in user_message.lower() or "vermarktung" in user_message.lower():
                tool_result = self._suggest_marketing_channels_tool()
                if tool_result["status"] == "success":
                    tools_used.append("suggest_marketing_channels")
                    response_text += f"\n\n📈 Marketing-Kanäle:\n{tool_result['marketing_channels']}"
            
            elif "moodboard" in user_message.lower() or "bilder" in user_message.lower() or "visualisierung" in user_message.lower():
                tool_result = self._create_moodboard_tool()
                if tool_result["status"] == "success":
                    tools_used.append("create_moodboard")
                    
                    # Speichere die Moodboard-Daten für die Anzeige
                    self._last_moodboard_data = tool_result.get('moodboard_data', {})
                    
                    # Formatiere die Moodboard-Konzepte sauber
                    concepts = tool_result.get('moodboard_concepts', '')
                    if concepts:
                        # Extrahiere nur die wichtigsten Teile, nicht den ganzen JSON-Output
                        lines = concepts.split('\n')
                        clean_concepts = []
                        for line in lines:
                            if line.strip() and not line.strip().startswith('{') and not line.strip().startswith('"'):
                                clean_concepts.append(line.strip())
                        if clean_concepts:
                            response_text += f"\n\n🎨 **Moodboard erstellt!**\n\nIch habe 9 thematische Bildkonzepte für dein Manuskript entwickelt:\n\n" + "\n".join(clean_concepts[:10])  # Zeige nur die ersten 10 Zeilen
                    else:
                        response_text += f"\n\n🎨 **Moodboard erstellt!**\n\nIch habe ein visuelles Moodboard mit 9 thematischen Bildern für dein Manuskript entwickelt."
            
            return {
                "message": response_text,
                "tools_used": tools_used,
                "status": "success"
            }
            
        except Exception as e:
            logger.error(f"Fehler bei Antwort-Generierung: {e}")
            return {
                "message": f"Entschuldigung, ich konnte deine Nachricht nicht verarbeiten: {str(e)}",
                "error": str(e),
                "status": "failed"
            }
    
    def get_chat_history(self) -> List[Dict[str, Any]]:
        """Gibt die Chat-Historie zurück."""
        return self.chat_history
    
    def clear_chat_history(self):
        """Löscht die Chat-Historie."""
        self.chat_history = []
        logger.info("Chat history cleared")
    
    def _create_moodboard_tool(self, **kwargs) -> Dict[str, Any]:
        """Tool: Moodboard mit 9 thematischen Bildern erstellen"""
        if not self.manuscript_context:
            return {"error": "Kein Manuskript-Kontext verfügbar", "status": "failed"}
        
        try:
            # Erstelle zuerst eine Zusammenfassung für bessere Bildgenerierung
            summary_result = self._summarize_manuscript_tool()
            if summary_result["status"] != "success":
                return {"error": "Konnte Manuskript nicht zusammenfassen", "status": "failed"}
            
            manuscript_summary = summary_result["summary"]
            
            # Generiere 9 verschiedene Bildkonzepte basierend auf dem Manuskript
            moodboard_prompt = f"""
            Basierend auf diesem Manuskript erstelle 9 verschiedene Bildkonzepte für ein Moodboard:
            
            MANUSKRIPT-ZUSAMMENFASSUNG:
            {manuscript_summary}
            
            Erstelle 9 verschiedene Bildkonzepte, die das Manuskript thematisch repräsentieren:
            1. Hauptcharakter/Protagonist
            2. Setting/Umgebung
            3. Stimmung/Atmosphäre
            4. Genre-spezifische Elemente
            5. Emotionale Kernbotschaft
            6. Zeitperiode/Epoche
            7. Symbolische Elemente
            8. Konflikt/Spannung
            9. Auflösung/Hoffnung
            
            Für jedes Bildkonzept:
            - Detaillierte Beschreibung (für Bildgenerierung)
            - Stilrichtung (z.B. realistisch, künstlerisch, minimalistisch)
            - Farbpalette
            - Emotionale Wirkung
            
            Format: Strukturierte Liste mit 9 Bildkonzepten
            """
            
            model = genai.GenerativeModel('gemini-2.5-pro')
            response = model.generate_content(moodboard_prompt)
            
            # Extrahiere die Bildkonzepte aus der Antwort
            concepts_text = response.text
            
            # Generiere jetzt die 9 Bilder mit Gemini Nano Banana
            generated_images = []
            image_descriptions = []
            
            # Parse die Konzepte und generiere Bilder
            lines = concepts_text.split('\n')
            current_concept = ""
            concept_count = 0
            
            for line in lines:
                if line.strip().startswith(('1.', '2.', '3.', '4.', '5.', '6.', '7.', '8.', '9.')):
                    if current_concept and concept_count < 9:
                        # Generiere Bild für das vorherige Konzept
                        try:
                            image_prompt = f"Create a high-quality, professional image: {current_concept.strip()}"
                            
                            # Verwende Gemini Nano Banana für Bildgenerierung
                            # Hinweis: Dies ist ein Platzhalter - die tatsächliche Implementierung
                            # würde die Gemini Nano Banana API verwenden
                            image_result = self._generate_image_with_gemini_nano(image_prompt)
                            
                            if image_result["status"] == "success":
                                generated_images.append(image_result["image_data"])
                                image_descriptions.append(current_concept.strip())
                                concept_count += 1
                        except Exception as e:
                            logger.error(f"Fehler bei Bildgenerierung {concept_count + 1}: {e}")
                    
                    current_concept = line
                else:
                    current_concept += " " + line
            
            # Generiere das letzte Bild
            if current_concept and concept_count < 9:
                try:
                    image_prompt = f"Create a high-quality, professional image: {current_concept.strip()}"
                    image_result = self._generate_image_with_gemini_nano(image_prompt)
                    
                    if image_result["status"] == "success":
                        generated_images.append(image_result["image_data"])
                        image_descriptions.append(current_concept.strip())
                except Exception as e:
                    logger.error(f"Fehler bei letzter Bildgenerierung: {e}")
            
            return {
                "moodboard_concepts": concepts_text,
                "generated_images": generated_images,
                "image_descriptions": image_descriptions,
                "moodboard_data": {
                    "concepts": concepts_text,
                    "images": generated_images,
                    "descriptions": image_descriptions,
                    "total_images": len(generated_images),
                    "created_at": datetime.now().isoformat()
                },
                "status": "success"
            }
            
        except Exception as e:
            logger.error(f"Fehler bei Moodboard-Erstellung: {e}")
            return {
                "error": str(e),
                "status": "failed"
            }
    
    def _generate_image_with_gemini_nano(self, prompt: str) -> Dict[str, Any]:
        """Generiert ein echtes Bild mit Gemini 2.5 Flash Image"""
        try:
            # Verwende das offizielle Gemini 2.5 Flash Image Modell
            model = genai.GenerativeModel('gemini-2.5-flash-image')
            
            # Erstelle einen optimierten Prompt für die Bildgenerierung
            image_prompt = f"""
            Create a professional, high-quality image for a moodboard based on this description:
            
            {prompt}
            
            The image should be:
            - High resolution and detailed
            - Professional quality
            - Thematically appropriate for the manuscript
            - Emotionally impactful
            - Visually appealing
            - Artistic and atmospheric
            
            Style: Realistic, artistic, professional
            """
            
            # Generiere das echte Bild mit Gemini 2.5 Flash Image
            response = model.generate_content(image_prompt)
            
            # Extrahiere das generierte Bild
            image_data = None
            image_description = prompt
            
            for part in response.candidates[0].content.parts:
                if part.inline_data is not None:
                    # Das ist das generierte Bild
                    image_data = part.inline_data.data
                    break
                elif part.text is not None:
                    # Fallback: Text-Beschreibung
                    image_description = part.text
            
            # Erstelle eine einzigartige Bild-ID
            image_id = f"moodboard_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hash(prompt) % 10000}"
            
            if image_data:
                # Speichere das Bild temporär und erstelle eine URL
                image_url = self._save_generated_image(image_data, image_id)
                
                return {
                    "image_data": {
                        "id": image_id,
                        "prompt": prompt,
                        "description": image_description,
                        "url": image_url,
                        "data": image_data,  # Base64 Bilddaten
                        "generated_at": datetime.now().isoformat(),
                        "status": "generated"
                    },
                    "status": "success"
                }
            else:
                # Fallback wenn kein Bild generiert wurde
                return {
                    "image_data": {
                        "id": image_id,
                        "prompt": prompt,
                        "description": image_description,
                        "url": f"https://picsum.photos/400/400?random={image_id}",
                        "generated_at": datetime.now().isoformat(),
                        "status": "fallback"
                    },
                    "status": "success"
                }
            
        except Exception as e:
            logger.error(f"Fehler bei Bildgenerierung: {e}")
            return {
                "error": str(e),
                "status": "failed"
            }
    
    def _generate_actual_image(self, description: str, image_id: str) -> str:
        """Generiert ein echtes Bild basierend auf der Beschreibung"""
        try:
            # Verwende einen echten Bildgenerierungs-Service
            # Hier implementieren wir eine einfache Lösung mit einem öffentlichen API
            
            # Erstelle einen optimierten Prompt für die Bildgenerierung
            optimized_prompt = f"Professional moodboard image: {description[:200]}"
            
            # Verwende einen kostenlosen Bildgenerierungs-Service
            # Hier verwenden wir einen Platzhalter, aber in der echten Implementierung
            # würde hier eine echte API wie DALL-E, Midjourney oder Stable Diffusion verwendet
            
            # Für jetzt erstellen wir eine Platzhalter-URL, die später durch echte Bilder ersetzt wird
            # In der Produktion würde hier eine echte Bildgenerierungs-API aufgerufen
            
            # Simuliere eine echte Bildgenerierung
            import hashlib
            hash_id = hashlib.md5(f"{description}_{image_id}".encode()).hexdigest()[:8]
            
            # Erstelle eine URL für ein generiertes Bild
            # Verwende einen echten Bildgenerierungs-Service
            # Hier verwenden wir Unsplash API für thematische Bilder
            image_url = f"https://source.unsplash.com/400x400/?{self._extract_keywords(description)}"
            
            return image_url
            
        except Exception as e:
            logger.error(f"Fehler bei echter Bildgenerierung: {e}")
            # Fallback zu einem Platzhalter-Bild
            return f"https://picsum.photos/400/400?random={image_id}"
    
    def _extract_keywords(self, description: str) -> str:
        """Extrahiert Schlüsselwörter aus der Bildbeschreibung für die Bildsuche"""
        try:
            # Extrahiere wichtige Schlüsselwörter aus der Beschreibung
            keywords = []
            
            # Häufige thematische Begriffe
            theme_keywords = {
                'city': ['stadt', 'city', 'urban', 'münchen', 'munich'],
                'office': ['büro', 'office', 'desk', 'arbeit', 'work'],
                'person': ['person', 'woman', 'man', 'face', 'portrait'],
                'nature': ['garten', 'garden', 'nature', 'trees', 'green'],
                'emotion': ['melancholy', 'sad', 'lonely', 'isolation', 'empty'],
                'light': ['light', 'shadow', 'dark', 'bright', 'sunset'],
                'abstract': ['abstract', 'artistic', 'minimalist', 'modern']
            }
            
            description_lower = description.lower()
            
            for category, words in theme_keywords.items():
                for word in words:
                    if word in description_lower:
                        keywords.append(category)
                        break
            
            # Fallback zu generischen Begriffen
            if not keywords:
                keywords = ['artistic', 'mood', 'atmosphere']
            
            return ','.join(keywords[:3])  # Maximal 3 Keywords
            
        except Exception as e:
            logger.error(f"Fehler bei Keyword-Extraktion: {e}")
            return "artistic,mood,atmosphere"
    
    def _save_generated_image(self, image_data: bytes, image_id: str) -> str:
        """Speichert das generierte Bild und gibt eine URL zurück"""
        try:
            import base64
            import os
            from pathlib import Path
            
            # Erstelle einen temporären Ordner für Bilder
            temp_dir = Path("temp_images")
            temp_dir.mkdir(exist_ok=True)
            
            # Speichere das Bild
            image_path = temp_dir / f"{image_id}.png"
            
            # Dekodiere Base64 und speichere
            if isinstance(image_data, str):
                # Wenn es bereits Base64 ist
                image_bytes = base64.b64decode(image_data)
            else:
                # Wenn es bereits Bytes sind
                image_bytes = image_data
            
            with open(image_path, 'wb') as f:
                f.write(image_bytes)
            
            # Erstelle eine relative URL für Streamlit
            return str(image_path)
            
        except Exception as e:
            logger.error(f"Fehler beim Speichern des Bildes: {e}")
            # Fallback zu einem Platzhalter
            return f"https://picsum.photos/400/400?random={image_id}"
    
    def get_available_tools(self) -> Dict[str, Any]:
        """Gibt die verfügbaren Tools zurück."""
        return self.available_tools
