import pytest
from src.core.categorizer import categorizza_con_regole


class TestCategorizer:

    @pytest.mark.parametrize("causale,categoria_attesa", [
        ("PAGAMENTO POS CONAD CITY", "Spesa"),
        ("Spesa presso Bennet Moncalieri", "Spesa"),
        ("ACCREDITO STIPENDIO AZIENDA SPA", "Entrate & Rimborsi"),
        ("SDD ENEL ENERGIA LUCE E GAS", "Utenze & Casa"),
        ("Ricarica telefonica TIM linea mobile", "Utenze & Casa"),
        ("RIFORNIMENTO Q8 EASY SELF", "Trasporti & Carburante"),
        ("Biglietteria TRENITALIA Roma Termini", "Trasporti & Carburante"),
        ("Pizzeria Da Michele cena", "Ristorazione"),
        ("Deliveroo Food Delivery", "Ristorazione"),
        ("ABBONAMENTO SPOTIFY PREMIUM", "Abbonamenti & Servizi Digitali"),
        ("Apple Services icloud storage 50gb", "Abbonamenti & Servizi Digitali"),
        ("Acquisto Amazon EU Sarl", "Shopping"),
        ("ZARA TORINO VIA ROMA", "Shopping"),
        ("FARMACIA COMUNALE SCONTRINO", "Salute & Benessere"),
        ("Cinema Massimo Torino biglietti", "Svago e Tempo Libero"),
    ])
    def test_categorizzazione_pattern_noti(self, causale, categoria_attesa):
        cat = categorizza_con_regole(causale)
        assert cat == categoria_attesa

    def test_priorita_giroconto(self):
        """Verifica che i trasferimenti e ricariche interne abbiano priorità assoluta."""
        assert categorizza_con_regole("Ricarica Satispay da conto") == "Giroconto"
        assert categorizza_con_regole("Giroconto verso conto deposito") == "Giroconto"
        assert categorizza_con_regole("Verso la Banca risparmi") == "Giroconto"

    def test_case_insensitivity(self):
        assert categorizza_con_regole("esselunga") == "Spesa"
        assert categorizza_con_regole("ESSELUNGA") == "Spesa"
        assert categorizza_con_regole("EsSeLuNgA") == "Spesa"

    def test_fallback_non_categorizzato(self):
        assert categorizza_con_regole("PAGAMENTO MISTERIOSO XYZ 999") == "Non Categorizzato"
        assert categorizza_con_regole("") == "Non Categorizzato"
        assert categorizza_con_regole(None) == "Non Categorizzato"