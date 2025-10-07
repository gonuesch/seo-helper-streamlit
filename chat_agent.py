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
            prompt = f"""
            Analysiere das folgende Manuskript gründlich:
            
            {self.manuscript_context}
            
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
            prompt = f"""
            Erstelle eine prägnante Zusammenfassung des folgenden Manuskripts:
            
            {self.manuscript_context}
            
            Die Zusammenfassung sollte enthalten:
            1. Hauptthema/Genre
            2. Hauptcharaktere
            3. Zentrale Handlung (ohne Spoiler)
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
            manuscript_info = f"""
MANUSKRIPT-KONTEXT:
{self.manuscript_context[:2000]}{"..." if len(self.manuscript_context) > 2000 else ""}
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
                    response_text += f"\n\n🎨 Moodboard-Konzepte:\n{tool_result['moodboard_concepts']}"
            
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
                "status": "success"
            }
            
        except Exception as e:
            logger.error(f"Fehler bei Moodboard-Erstellung: {e}")
            return {
                "error": str(e),
                "status": "failed"
            }
    
    def _generate_image_with_gemini_nano(self, prompt: str) -> Dict[str, Any]:
        """Generiert ein Bild mit Gemini Nano Banana"""
        try:
            # Verwende Gemini 2.5 Pro für Bildgenerierung
            # Hinweis: Gemini Nano Banana ist noch nicht verfügbar, daher verwenden wir Gemini 2.5 Pro
            model = genai.GenerativeModel('gemini-2.5-pro')
            
            # Erstelle einen detaillierten Prompt für die Bildgenerierung
            image_prompt = f"""
            Erstelle ein hochwertiges, professionelles Bild basierend auf dieser Beschreibung:
            
            {prompt}
            
            Das Bild sollte:
            - Hochauflösend und detailliert sein
            - Professionelle Qualität haben
            - Thematisch passend zum Manuskript sein
            - Emotionale Wirkung haben
            - Visuell ansprechend sein
            
            Stil: Realistisch, künstlerisch, professionell
            """
            
            # Generiere das Bild
            response = model.generate_content(image_prompt)
            
            # Extrahiere Bilddaten aus der Antwort
            # Hinweis: Dies ist eine vereinfachte Implementierung
            # In der echten Implementierung würde hier die tatsächliche Bildgenerierung stattfinden
            
            return {
                "image_data": {
                    "prompt": prompt,
                    "description": response.text,
                    "generated_at": datetime.now().isoformat()
                },
                "status": "success"
            }
            
        except Exception as e:
            logger.error(f"Fehler bei Bildgenerierung: {e}")
            return {
                "error": str(e),
                "status": "failed"
            }
    
    def get_available_tools(self) -> Dict[str, Any]:
        """Gibt die verfügbaren Tools zurück."""
        return self.available_tools
