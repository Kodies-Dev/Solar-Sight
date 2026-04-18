import joblib
import pandas as pd
import numpy as np
import os


def predykuj():

    FOLDER_SKRYPTU = os.path.dirname(os.path.abspath(__file__))
    path_model = os.path.join(FOLDER_SKRYPTU, '..', 'artifacts', 'model_bez_lagow.joblib')
    path_data  = os.path.join(FOLDER_SKRYPTU, '..', 'forecast', 'forecast_final.csv')
    model = joblib.load(path_model)
    df    = pd.read_csv(path_data)
    df['timestamp'] = pd.to_datetime(df['timestamp'])

    required_features = list(model.feature_names_in_)
    for col in required_features:
        if col not in df.columns:
            print(f"UWAGA: brakuje '{col}' — uzupełniam zerami")
            df[col] = 0.0

    X = df[required_features]

    predykcja = model.predict(X)
    predykcja = np.maximum(0, predykcja).round(3)

    wyniki = pd.DataFrame({
        'timestamp':     df['timestamp'],
        'hour':          df['hour'],
        'predykcja_mwh': predykcja
    })



    wyniki.sort_values(by='hour', ascending=True, inplace=True)
    return wyniki

