from unittest.mock import MagicMock
import numpy as np
import pandas as pd
import pytest
from src.core.vector_store import VectorStore, normalizza_per_embedding


class TestVectorStoreNormalization:

    def test_normalizza_per_embedding(self):
        testo = "PAGAMENTO POS 12/05/2024 ORE 14:30 [CARTA] DR BIANCHI FISIOTERAPIA"
        pulito = normalizza_per_embedding(testo)
        
        # Devono sparire date, ore, token [carta], stopwords come pos/pagamento/dr
        assert "12/05/2024" not in pulito
        assert "14:30" not in pulito
        assert "[carta]" not in pulito
        assert "pos" not in pulito
        assert "dr" not in pulito
        assert "bianchi" in pulito
        assert "fisioterapia" in pulito


class TestVectorStoreEngine:

    @pytest.fixture
    def mock_vector_store(self, mocker):
        """Crea un VectorStore con SentenceTransformer e DB completamente mockati."""
        mock_encoder = MagicMock()
        # Genera vettori dimensionalità 384 normalizzati fittizi
        mock_encoder.encode.side_effect = lambda texts, **kwargs: np.ones((len(texts), 384), dtype=np.float32)

        mocker.patch("src.core.vector_store.SentenceTransformer", return_value=mock_encoder)
        mocker.patch(
            "src.core.vector_store.run_query",
            return_value=pd.DataFrame({
                "Id": [101, 102],
                "Causale": ["PAGAMENTO POS BENNET", "ENI STATION BENZINA"],
                "Categoria": ["Spesa", "Trasporti & Carburante"]
            })
        )

        vs = VectorStore()
        return vs

    def test_inizializzazione_seed(self, mock_vector_store):
        assert len(mock_vector_store.categorie) > 0
        assert mock_vector_store.embeddings is not None
        assert mock_vector_store.embeddings.shape[1] == 384

    def test_cerca_esempi_simili(self, mock_vector_store):
        risultati = mock_vector_store.cerca_esempi_simili("Supermercato Pam Spesa", k=2)
        assert len(risultati) == 2
        assert "causale" in risultati[0]
        assert "categoria" in risultati[0]
        assert "similarita" in risultati[0]

    def test_ricarica_indice_incrementale(self, mock_vector_store, mocker):
        conteggio_iniziale = len(mock_vector_store.categorie)

        # Simula il salvataggio di una nuova transazione nel DB
        mocker.patch(
            "src.core.vector_store.run_query",
            return_value=pd.DataFrame({
                "Id": [101, 102, 103],
                "Causale": ["PAGAMENTO POS BENNET", "ENI STATION BENZINA", "ZARA ABBIGLIAMENTO"],
                "Categoria": ["Spesa", "Trasporti & Carburante", "Shopping"]
            })
        )

        mock_vector_store.ricarica_indice()
        assert len(mock_vector_store.categorie) == conteggio_iniziale + 1
        assert 103 in mock_vector_store.ids_caricati