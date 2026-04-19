# SolarSight
Team: Jakub Bodzioch, Kajetan Hołdan, Igor Kotlarz, Kamil Musioł, Jan Piechota, Łukasz Wolf

**ETHSilesia / Tauron AI Hackathon 2026 — Team SolarSight**

**Concept:** System predykcji godzinowej produkcji energii z fotowoltaiki na 24 godziny do przodu, oparty na danych pogodowych i historycznej produkcji krajowej. Narzędzie wspierające operatorów sieci dystrybucyjnej w planowaniu pracy jednostek konwencjonalnych, redukcji nadwyżek i deficytów oraz minimalizacji emisji CO₂.


## Co składa się na nasze rozwiązanie?

- **Model uczenia maszynowego** *(Python / XGBoost / Optuna)* - przewiduje godzinową produkcję energii ze słońca na 24 godziny do przodu, z bardzo wysoką dokładnością na danych testowych.
- **Pobieranie i przetwarzanie danych** *(Python / pandas)* - automatyczne pobieranie danych pogodowych i historycznej produkcji PV z publicznych źródeł, czyszczenie i przygotowanie do treningu modelu.
- **Prognoza w czasie rzeczywistym** *(Open-Meteo API + Google Weather API)* - łączenie aktualnych prognoz pogody z dwóch niezależnych źródeł, by zwiększyć precyzję predykcji.
- **Frontend** *(React / Mapbox)* - interaktywna mapa Polski z punktami miast; po kliknięciu wyświetla godzinową prognozę produkcji dla wybranej lokalizacji.
- **Backend** *(Python / Flask)* - udostępnia predykcje modelu aplikacji frontendowej.

## Struktura repozytorium

- `Projekt model panele/` - model, pipeline danych, frontend i backend
- `LICENSE` - GNU General Public License v3.0
- `SOURCE.txt` - informacja o pochodzeniu projektu

## Źródła danych

Wszystkie wykorzystane źródła danych są publiczne i bezpłatne:

- [Open-Meteo](https://open-meteo.com) - dane pogodowe historyczne i prognozy
- [ENTSO-E](https://transparency.entsoe.eu) via [instrat.pl](https://energy-api.instrat.pl) - krajowa produkcja PV
- [URE](https://www.ure.gov.pl) - moc zainstalowana fotowoltaiki w Polsce (dane miesięczne)
- [Google Weather API](https://developers.google.com/maps/documentation/weather) - prognoza pogodowa (wymaga klucza API)

## Demo
[Video presentation](https://youtu.be/C_B6lFZmzMw)

## License

This project is licensed under the GNU General Public License v3.0 - see the [LICENSE](LICENSE) file for details.
