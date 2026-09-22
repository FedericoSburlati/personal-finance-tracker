import json
from unittest.mock import MagicMock
import pytest
from src.core.llm_classifier import classifica_con_rag


class TestLLMClassifier:

    def test_forte_affinità_bypass_llm(self, mocker):
        """Se la similarità è >= 0.85, deve restituire il match RAG senza chiamare Ollama."""
        mock_vs = MagicMock()
        mock_vs.cerca_esempi_simili.return_value = [
            {"causale": "Conad Supermercato", "categoria": "Spesa", "similarita": 0.92}
        ]
        mocker.patch("src.core.llm_classifier.get_vector_store", return_value=mock_vs)
        mock_ollama = mocker.patch("src.core.llm_classifier.ollama.chat")

        risultato = classifica_con_rag("Conad Spesa Alimentare", -30.0, "Intesa Sanpaolo")

        assert risultato["categoria"] == "Spesa"
        assert risultato["metodo"] == "RAG Diretto (A)"
        assert risultato["confidenza"] >= 0.90
        # Ollama NON deve essere stato chiamato
        mock_ollama.assert_not_called()

    def test_parziale_affinità_few_shot(self, mocker):
        """Tra 0.40 e 0.85 deve iniettare gli esempi nel prompt e chiamare Ollama."""
        mock_vs = MagicMock()
        mock_vs.cerca_esempi_simili.return_value = [
            {"causale": "Decathlon Grugliasco", "categoria": "Shopping", "similarita": 0.65}
        ]
        mocker.patch("src.core.llm_classifier.get_vector_store", return_value=mock_vs)

        mock_ollama = mocker.patch("src.core.llm_classifier.ollama.chat")
        mock_ollama.return_value = {
            "message": {
                "content": json.dumps({
                    "categoria": "Shopping",
                    "confidenza": 0.88,
                    "motivo": "Articoli sportivi analoghi a Decathlon"
                })
            }
        }

        risultato = classifica_con_rag("Nike Store Scarpe", -85.0, "Hype")

        assert risultato["categoria"] == "Shopping"
        assert risultato["metodo"] == "LLM Dynamic Few-Shot (Parziale Affinità)"
        mock_ollama.assert_called_once()
        
        # Verifica che il prompt contenga gli esempi storici iniettati
        chiamata_messages = mock_ollama.call_args[1]["messages"]
        system_content = chiamata_messages[0]["content"]
        assert "ESEMPI STORICI REALI" in system_content
        assert "Decathlon Grugliasco" in system_content

    def test_scarsa_affinità_zero_shot(self, mocker):
        """Sotto 0.40 non deve iniettare esempi storici."""
        mock_vs = MagicMock()
        mock_vs.cerca_esempi_simili.return_value = [
            {"causale": "Sconosciuto", "categoria": "Svago e Tempo Libero", "similarita": 0.20}
        ]
        mocker.patch("src.core.llm_classifier.get_vector_store", return_value=mock_vs)

        mock_ollama = mocker.patch("src.core.llm_classifier.ollama.chat")
        mock_ollama.return_value = {
            "message": {
                "content": json.dumps({
                    "categoria": "Non Categorizzato",
                    "confidenza": 0.30,
                    "motivo": "Causale incomprensibile"
                })
            }
        }

        risultato = classifica_con_rag("Transazione Anomala 123", -10.0, "Intesa Sanpaolo")

        assert risultato["metodo"] == "LLM Zero-Shot (Scarsa Affinità)"
        mock_ollama.assert_called_once()

    def test_resilienza_fallimento_ollama(self, mocker):
        """Se il demone Ollama va in timeout o crasha, il codice non deve sollevare eccezioni non gestite."""
        mock_vs = MagicMock()
        mock_vs.cerca_esempi_simili.return_value = []
        mocker.patch("src.core.llm_classifier.get_vector_store", return_value=mock_vs)

        mocker.patch("src.core.llm_classifier.ollama.chat", side_effect=ConnectionError("Ollama service down"))

        risultato = classifica_con_rag("Qualsiasi causale", -20.0, "Hype")

        assert risultato["categoria"] == "Non Categorizzato"
        assert risultato["confidenza"] == 0.0
        assert "Errore inferenza" in risultato["motivo"]