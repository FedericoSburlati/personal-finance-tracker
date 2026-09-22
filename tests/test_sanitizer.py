import pytest
from src.core.sanitizer import maschera_dati_sensibili


class TestSanitizer:

    def test_maschera_iban(self):
        testo = "Disposizione bonifico verso IT02L1234512345000000123456 per affitto"
        risultato = maschera_dati_sensibili(testo)
        assert "IT02L1234512345000000123456" not in risultato
        assert "[IBAN]" in risultato
        assert "affitto" in risultato

    def test_maschera_carte_credito_e_mascherate(self):
        casi = [
            ("PAGAMENTO CARTA 5355 7890 1234 5678 ESERCENTE", "[CARTA]"),
            ("PAGAMENTO CARTA 5355-7890-1234-5678 ESERCENTE", "[CARTA]"),
            ("POS **** **** **** 1234 BAR CENTRO", "[CARTA]"),
            ("POS **** 1234 NEGOZIO", "[CARTA]"),
        ]
        for testo, token_atteso in casi:
            res = maschera_dati_sensibili(testo)
            assert token_atteso in res

    def test_maschera_codice_fiscale(self):
        testo = "Fattura emessa a favore di RSSMRA85M01H501Z visita medica"
        risultato = maschera_dati_sensibili(testo)
        assert "RSSMRA85M01H501Z" not in risultato
        assert "[CF]" in risultato
        assert "visita medica" in risultato

    def test_maschera_nominativi_in_bonifici(self):
        testo = "ACCREDITO BONIFICO DA MARIO ROSSI NOTA SALDO DEBITO"
        risultato = maschera_dati_sensibili(testo)
        assert "MARIO ROSSI" not in risultato
        assert "[NOME]" in risultato
        assert "SALDO DEBITO" in risultato

    def test_preservazione_merchant_legittimi(self):
        """Assicura che i nomi dei commercianti o brand non vengano erroneamente oscurati."""
        testi = [
            "PAGAMENTO POS ESSELUNGA MILANO",
            "ADDEBITO MENSILE NETFLIX ENTERTAINMENT",
            "RIFORNIMENTO ENI STATION TORINO",
            "ACQUISTO DECATHLON ONLINE",
        ]
        for t in testi:
            res = maschera_dati_sensibili(t)
            assert res == t, f"La causale '{t}' è stata alterata in '{res}'"

    def test_gestione_input_non_validi(self):
        assert maschera_dati_sensibili("") == ""
        assert maschera_dati_sensibili(None) == ""
        assert maschera_dati_sensibili(12345) == ""