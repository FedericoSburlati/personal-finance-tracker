import io
import pandas as pd
import pytest
from src.etl.etl import calcola_hash, clean_amount, parse_intesa, parse_hype, parse_satispay, salva_transazioni


class TestETLAmountAndHash:

    def test_calcola_hash_idempotente(self):
        h1 = calcola_hash("2024-05-10", -15.50, "Caffè Bar Centro")
        h2 = calcola_hash("2024-05-10", -15.50, "  caffè bar centro  ")
        h3 = calcola_hash("2024-05-10", -15.50, "Altro Bar")
        
        # Stesso importo, data e causale normalizzata devono produrre lo stesso hash
        assert h1 == h2
        # Causale diversa deve produrre hash differente
        assert h1 != h3

    @pytest.mark.parametrize("valore_input,valore_atteso", [
        (10.5, 10.5),
        (-25, -25.0),
        ("15,50", 15.50),
        ("-1.250,99 €", -1250.99),
        ("2.400,00", 2400.00),
        ("99.99", 99.99),
        ("- 45,00 €", -45.00),
        (None, 0.0),
        (float("nan"), 0.0),
    ])
    def test_clean_amount(self, valore_input, valore_atteso):
        assert clean_amount(valore_input) == pytest.approx(valore_atteso, rel=1e-3)


class TestBankParsers:

    def test_parse_intesa_sanpaolo(self, sample_raw_intesa_csv):
        file_obj = io.BytesIO(sample_raw_intesa_csv.encode("latin-1"))
        df = parse_intesa(file_obj)

        assert len(df) == 2
        assert list(df.columns) == ["Data", "Importo", "Causale", "Banca"]
        assert df.iloc[0]["Importo"] == -45.80
        assert df.iloc[0]["Banca"] == "Intesa Sanpaolo"
        assert "Supermercato Conad" in df.iloc[0]["Causale"]
        assert df.iloc[1]["Importo"] == 1500.00

    def test_parse_intesa_header_mancante(self):
        file_invalido = io.BytesIO(b"ColonnaA;ColonnaB\nValore1;Valore2\n")
        with pytest.raises(ValueError, match="Header non trovato"):
            parse_intesa(file_invalido)

    def test_parse_hype(self, sample_raw_hype_csv):
        file_obj = io.BytesIO(sample_raw_hype_csv.encode("utf-8"))
        df = parse_hype(file_obj)

        assert len(df) == 2
        assert df.iloc[0]["Banca"] == "Hype"
        assert df.iloc[0]["Importo"] == -12.50
        assert "Pizzeria Da Mario" in df.iloc[0]["Causale"]

    def test_parse_satispay(self, sample_raw_satispay_csv):
        file_obj = io.BytesIO(sample_raw_satispay_csv.encode("utf-8"))
        df = parse_satispay(file_obj)

        # Il record con stato "Rifiutato" deve essere scartato
        assert len(df) == 2
        assert df.iloc[0]["Importo"] == -1.50
        # Il deposito salvadanaio deve essere taggato come [GIROCONTO]
        assert "[GIROCONTO]" in df.iloc[1]["Causale"]


class TestSalvaTransazioni:

    def test_deduplicazione_e_salvataggio(self, mocker):
        # Simula che il DB contenga già un hash "HASH_ESISTENTE"
        mocker.patch(
            "src.etl.etl.run_query",
            return_value=pd.DataFrame({"Hash_Duplicato": ["HASH_ESISTENTE"]})
        )
        mock_exec = mocker.patch("src.etl.etl.execute_query")

        df_da_inserire = pd.DataFrame([
            {"Data": "2024-05-01", "Importo": -10.0, "Causale": "Spesa 1", "Banca": "Hype", "Hash_Duplicato": "HASH_ESISTENTE"}, # duplicato DB
            {"Data": "2024-05-02", "Importo": -20.0, "Causale": "Spesa 2", "Banca": "Hype", "Hash_Duplicato": "HASH_NUOVO_1"},     # nuovo
            {"Data": "2024-05-02", "Importo": -20.0, "Causale": "Spesa 2", "Banca": "Hype", "Hash_Duplicato": "HASH_NUOVO_1"},     # duplicato interno al file
        ])

        inseriti, duplicati = salva_transazioni(df_da_inserire)

        assert inseriti == 1
        assert duplicati == 2
        assert mock_exec.call_count == 1