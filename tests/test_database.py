from unittest.mock import MagicMock
import pandas as pd
import pytest
from src.database.db import run_query, execute_query


class TestDatabaseWrappers:

    def test_run_query_restituisce_dataframe(self, mock_db_connection, mocker):
        # Simula pd.read_sql
        df_atteso = pd.DataFrame({"Id": [1, 2], "Importo": [10.5, -20.0]})
        mocker.patch("src.database.db.pd.read_sql", return_value=df_atteso)

        risultato = run_query("SELECT * FROM TRANSAZIONE WHERE Importo > :val", params={"val": 0})

        assert isinstance(risultato, pd.DataFrame)
        assert len(risultato) == 2
        assert list(risultato["Importo"]) == [10.5, -20.0]

    def test_execute_query_singola(self, mock_db_connection):
        execute_query("UPDATE TRANSAZIONE SET Categoria = :cat WHERE Id = :id", params={"cat": "Spesa", "id": 1})
        mock_db_connection.execute.assert_called_once()

    def test_execute_query_batch(self, mock_db_connection):
        batch_params = [
            {"cat": "Spesa", "id": 1},
            {"cat": "Ristorazione", "id": 2},
        ]
        execute_query("UPDATE TRANSAZIONE SET Categoria = :cat WHERE Id = :id", params=batch_params)
        mock_db_connection.execute.assert_called_once()
        # Verifica che il secondo argomento passato a conn.execute sia la lista dei parametri
        _, kwargs_o_args = mock_db_connection.execute.call_args
        assert batch_params in mock_db_connection.execute.call_args[0]