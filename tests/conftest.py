import sys
from pathlib import Path
from unittest.mock import MagicMock
import numpy as np
import pandas as pd
import pytest

# Garantisce che la root del progetto sia sempre visibile agli import
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


@pytest.fixture
def mock_db_connection(mocker):
    """Mock della connessione SQLAlchemy per evitare dipendenze da un MySQL reale."""
    mock_conn = MagicMock()
    mock_engine = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn
    mock_engine.begin.return_value.__enter__.return_value = mock_conn
    mocker.patch("src.database.db.engine", mock_engine)
    return mock_conn


@pytest.fixture
def sample_raw_intesa_csv():
    """Simula il contenuto grezzo di un estratto conto Intesa Sanpaolo con righe di preambolo."""
    content = (
        "Informazioni di test...\n"
        "Data;Operazione;Dettagli;Conto o Carta;Contabilizzazione;Categoria;Importo\n"
        "12/05/2024;PAGAMENTO POS;Supermercato Conad;Carta 1234;13/05/2024;Spesa;-45,80\n"
        "15/05/2024;BONIFICO ACCREDITO;Stipendio Maggio;Conto;15/05/2024;Entrate;1.500,00\n"
    )
    return content


@pytest.fixture
def sample_raw_hype_csv():
    """Simula il contenuto di un export CSV di Hype."""
    content = (
        "Data Operazione;Importo;Tipologia;Nome;Descrizione\n"
        "10/06/2024;-12,50;Pagamento;Pizzeria Da Mario;Cena con amici\n"
        "11/06/2024;50,00;Ricarica;Mario Rossi;Rimborso quota\n"
    )
    return content


@pytest.fixture
def sample_raw_satispay_csv():
    """Simula il contenuto di un export CSV di Satispay."""
    content = (
        "Data;Stato;Tipo;Nome;Descrizione;Importo\n"
        "2024-04-01 12:00:00;Approvato;P2P;Marco Bianchi;Caffè;-1.50\n"
        "2024-04-02 15:30:00;Rifiutato;Business;Bar Test;Non addebitato;-3.00\n"
        "2024-04-03 08:00:00;Approvato;Deposito;Verso la Banca;Salvadanaio;-50.00\n"
    )
    return content