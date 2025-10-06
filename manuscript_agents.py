# manuscript_agents.py - Vereinfachte Agents für Manuskript-Analyse

import logging
from typing import Dict, List, Any, Optional
import google.generativeai as genai
from pathlib import Path
import json
import asyncio

# Logging Setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ManuscriptAnalyzerAgent:
    """Agent für Manuskript-Analyse, Bewertung und Zusammenfassung."""
    
    def __init__(self, gemini_api_key: str):
        self.gemini_api_key = gemini_api_key
        if gemini_api_key:
            genai.configure(api_key=gemini_api_key)
    
    def analyze_manuscript(self, text: str) -> Dict[str, Any]:
        """Führt eine umfassende Manuskript-Analyse durch."""
        try:
            prompt = f"""
            Analysiere das folgende Manuskript gründlich:
            
            {text}
            
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
    
    def summarize_manuscript(self, text: str) -> Dict[str, Any]:
        """Erstellt eine prägnante Zusammenfassung des Manuskripts."""
        try:
            prompt = f"""
            Erstelle eine prägnante Zusammenfassung des folgenden Manuskripts:
            
            {text}
            
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
    
    def evaluate_manuscript(self, text: str) -> Dict[str, Any]:
        """Erstellt eine Gesamtbewertung des Manuskripts."""
        try:
            prompt = f"""
            Bewerte das folgende Manuskript und erstelle eine Gesamtbewertung:
            
            {text}
            
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


class TargetAudienceAgent:
    """Agent für Zielgruppen-Analyse und Werbewege."""
    
    def __init__(self, gemini_api_key: str):
        self.gemini_api_key = gemini_api_key
        if gemini_api_key:
            genai.configure(api_key=gemini_api_key)
    
    def analyze_target_audience(self, manuscript_summary: str) -> Dict[str, Any]:
        """Analysiert die Zielgruppe für ein Manuskript."""
        try:
            prompt = f"""
            Basierend auf diesem Manuskript analysiere die Zielgruppe:
            
            {manuscript_summary}
            
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
    
    def suggest_marketing_channels(self, manuscript_summary: str, target_audience: str) -> Dict[str, Any]:
        """Schlägt Marketing-Kanäle basierend auf Zielgruppe vor."""
        try:
            prompt = f"""
            Basierend auf diesem Manuskript und der Zielgruppe schlage Marketing-Kanäle vor:
            
            MANUSKRIPT: {manuscript_summary}
            ZIELGRUPPE: {target_audience}
            
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
    
    def create_marketing_strategy(self, manuscript_summary: str, target_audience: str, channels: str) -> Dict[str, Any]:
        """Erstellt eine umfassende Marketing-Strategie."""
        try:
            prompt = f"""
            Erstelle eine umfassende Marketing-Strategie:
            
            MANUSKRIPT: {manuscript_summary}
            ZIELGRUPPE: {target_audience}
            KANÄLE: {channels}
            
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


class MarketingStrategyAgent:
    """Agent für Marketing-Strategien und Targeting."""
    
    def __init__(self, gemini_api_key: str):
        self.gemini_api_key = gemini_api_key
        if gemini_api_key:
            genai.configure(api_key=gemini_api_key)
    
    def optimize_marketing_strategy(self, strategy: str, target_audience: str) -> Dict[str, Any]:
        """Optimiert eine Marketing-Strategie basierend auf Zielgruppe."""
        try:
            prompt = f"""
            Optimiere diese Marketing-Strategie für die Zielgruppe:
            
            STRATEGIE: {strategy}
            ZIELGRUPPE: {target_audience}
            
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
    
    def create_campaign_concept(self, manuscript_summary: str, target_audience: str, budget: str) -> Dict[str, Any]:
        """Erstellt ein detailliertes Kampagnen-Konzept."""
        try:
            prompt = f"""
            Erstelle ein detailliertes Kampagnen-Konzept:
            
            MANUSKRIPT: {manuscript_summary}
            ZIELGRUPPE: {target_audience}
            BUDGET: {budget}
            
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
    
    def analyze_roi(self, strategy: str, budget: str, expected_results: str) -> Dict[str, Any]:
        """Analysiert den ROI einer Marketing-Strategie."""
        try:
            prompt = f"""
            Analysiere den ROI dieser Marketing-Strategie:
            
            STRATEGIE: {strategy}
            BUDGET: {budget}
            ERWARTETE ERGEBNISSE: {expected_results}
            
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


class ManuscriptWorkflowAgent:
    """Workflow Agent für den kompletten Manuskript-Workflow."""
    
    def __init__(self, gemini_api_key: str):
        self.gemini_api_key = gemini_api_key
        self.manuscript_analyzer = ManuscriptAnalyzerAgent(gemini_api_key)
        self.target_audience = TargetAudienceAgent(gemini_api_key)
        self.marketing_strategy = MarketingStrategyAgent(gemini_api_key)
    
    async def process_manuscript(self, manuscript_text: str) -> Dict[str, Any]:
        """Verarbeitet ein Manuskript durch den kompletten Workflow."""
        try:
            results = {}
            
            # 1. Manuskript-Analyse
            analysis_result = self.manuscript_analyzer.analyze_manuscript(manuscript_text)
            summary_result = self.manuscript_analyzer.summarize_manuscript(manuscript_text)
            evaluation_result = self.manuscript_analyzer.evaluate_manuscript(manuscript_text)
            
            results["analysis"] = analysis_result
            results["summary"] = summary_result
            results["evaluation"] = evaluation_result
            
            # 2. Zielgruppen-Analyse
            if summary_result["status"] == "success":
                audience_result = self.target_audience.analyze_target_audience(summary_result["summary"])
                results["audience"] = audience_result
                
                if audience_result["status"] == "success":
                    channels_result = self.target_audience.suggest_marketing_channels(
                        summary_result["summary"], 
                        audience_result["audience_analysis"]
                    )
                    results["channels"] = channels_result
            
            # 3. Marketing-Strategie
            if "audience" in results and results["audience"]["status"] == "success":
                strategy_result = self.marketing_strategy.optimize_marketing_strategy(
                    summary_result["summary"],
                    results["audience"]["audience_analysis"]
                )
                results["strategy"] = strategy_result
            
            return {
                "workflow_result": results,
                "status": "success"
            }
        except Exception as e:
            logger.error(f"Fehler im Manuskript-Workflow: {e}")
            return {
                "error": str(e),
                "status": "failed"
            }