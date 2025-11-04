import pandas as pd
import streamlit as st
import yfinance as yf
from pathlib import Path
from datetime import date
from pandas.tseries.offsets import BDay
import matplotlib.pyplot as plt
from pandas.tseries.offsets import DateOffset

def charger_vues():
    path = Path("Data/Tickers.csv",header=1)
    tickers = pd.read_csv(path, sep=";")
    path2 = Path("Data/Vues.csv")
    vues = pd.read_csv(path2, sep=";",index_col=None)
    valeurs_autorisees = tickers["Tickers"].dropna().astype(str).tolist()
    
    valeurs_autorisees2=valeurs_autorisees.copy()
    valeurs_autorisees2.append("Tickers")

    vues = vues[vues["Tickers"].isin(valeurs_autorisees2)]
    vues = vues.loc[:, vues.columns.isin(valeurs_autorisees2)]
    
    colonnes_manquantes = [v for v in valeurs_autorisees if v not in vues.columns]
    for c in colonnes_manquantes:
        vues[c] = pd.NA
    
    # Ajouter les valeurs manquantes en lignes
    valeurs_existantes = vues["Tickers"].unique().tolist()
    lignes_manquantes = [v for v in valeurs_autorisees if v not in valeurs_existantes]
    for v in lignes_manquantes:
        nouvelle_ligne = pd.Series({col: pd.NA for col in vues.columns})
        nouvelle_ligne["Tickers"] = v
        vues = pd.concat([vues, nouvelle_ligne.to_frame().T], ignore_index=True)
    vues = vues.fillna(0.0)
    ordre = vues.columns.tolist()
    if "Tickers" in ordre:
        ordre.remove("Tickers")
    vues = vues.set_index("Tickers").reindex(ordre).reset_index()
    return vues
    
def modifier_vues(df):
    # Copier le DataFrame pour affichage
    df_display = df.copy()

    # Conversion en pourcentage pour toutes les colonnes sauf la première
    cols_to_scale = df_display.columns[1:]
    df_display[cols_to_scale] = df_display[cols_to_scale] * 100
    df_display[cols_to_scale] = df_display[cols_to_scale].round(2)

    # Affichage modifiable
    editable_df = st.data_editor(
        df_display,
        num_rows="fixed",
        disabled=[df_display.columns[0]],
        column_config={
            c: st.column_config.NumberColumn(format="%.2f %%") for c in cols_to_scale
        }
    )

    # Enregistrement en décimal lors de l'appui du bouton
    if st.button("Enregistrer en CSV"):
        df_to_save = editable_df.copy()
        df_to_save[cols_to_scale] = df_to_save[cols_to_scale] / 100
        df_to_save.to_csv("Data/Vues.csv", sep=";", index=False, float_format="%.6f")
        st.text('Enregistrement des vues fait !!')

def create_views_with_confidence(vues_csv_path, assets, confidences=None, tau=0.5, sigma=None):
    vues_df = pd.read_csv(vues_csv_path, sep=";", index_col=None)
    k = len(vues_df)
    n = len(assets)
    
    P = np.zeros((k, n))
    Q = np.zeros((k, 1))
    Omega = np.zeros((k, k))
    
    if confidences is None:
        confidences = [0.5] * k
    
    for i, row in vues_df.iterrows():
        for j, asset in enumerate(assets):
            P[i, j] = float(row.get(asset, 0.0))
        
        Q[i, 0] = float(row.get("ExpectedReturn", 0.0))   # A CHNAGER !! ca va dépendre de la structure de notre fichier csv de vues
        
        c = np.clip(confidences[i], 1e-6, 1-1e-6)
        if sigma is not None:
            base = P[i] @ (tau * sigma) @ P[i].T
            Omega[i, i] = ((1 - c) / c) * base
        else:
            Omega[i, i] = (1 - c) * 0.05
    return P, Q, Omega

def black_litterman(P, Q, sigma, tau, pi, omega, delta):
    part1 = np.linalg.inv(np.linalg.inv(tau*sigma) + P.T @ np.linalg.inv(omega) @ P)
    part2 = np.linalg.inv(tau*sigma) @ pi + P.T @ np.linalg.inv(omega) @ Q
    mu_bl = part1 @ part2
    w_bl = (1/delta) * np.linalg.inv(sigma) @ mu_bl
    return mu_bl, w_bl

def rdmt_anticipe_mkt(sigma, w_mkt,delta):
    #Pi = aversion * matrice covar * w_mkt
    return delta * sigma @ w_mkt


def black_litt():
    path = "Data/Data_Set_daily.csv"
    Data = pd.read_csv(path, sep=";", index_col="Date", parse_dates=["Date"])
    Data.index = pd.to_datetime(Data.index, errors="coerce",format="%d/%m/%Y")
    Data = Data.sort_index()
    
    limite = pd.Timestamp.today() - DateOffset(years=5)
    Data = Data[Data.index >= limite]
    
        
    st.subheader("Prix des actifs (5 dernières années)")
    st.dataframe(Data.tail(5))
    
    assets = list(data.columns)
    
    # Calcul des rendements mensuels
    returns = Data.resample("M").last().pct_change().dropna()
    sigma = returns.cov().values
    
    # 4. Poids du marché via market cap
    market_caps = []
    for ticker in assets:
        info = yf.Ticker(ticker).info
        mcap = info.get("marketCap", None)
        market_caps.append(mcap)
    market_caps = np.array([m if m is not None else np.mean([x for x in market_caps if x is not None]) for m in market_caps])
    w_mkt = (market_caps / np.sum(market_caps))[:, None]
    
    # 5. Calcul des rendements implicites du marché
    delta = 1.9
    tau = 0.5  # a voir comment def ces param
    pi=rdmt_anticipe_mkt(sigma, w_mkt,delta)
    
    # on cahrge les vues collectées
    vues_csv_path = Path("Data/Vues.csv")
    k = len(pd.read_csv(vues_csv_path))
    confidences = [0.5]*k  # Par def 50%, mais a voir ce qu on veut mettre 
    
    P, Q, Omega = create_views_with_confidence(vues_csv_path, assets, confidences, tau, sigma)
    
    mu_bl, w_bl = black_litterman(P, Q, sigma, tau, pi, Omega, delta)
    

    st.subheader("Rendements ajustés µ_BL")
    st.dataframe(pd.DataFrame(mu_bl, index=assets, columns=["µ_BL"]))
    
    st.subheader("Poids optimisés w_BL")
    w_df = pd.DataFrame({
        "Marché": w_mkt.flatten(),
        "Black-Litterman": w_bl.flatten()
    }, index=assets)
    st.dataframe(w_df)
    
    # graph mais a modif
    fig, ax = plt.subplots(figsize=(8,5))
    w_df.plot(kind="bar", ax=ax, title="Poids Marché vs Black–Litterman")
    ax.set_ylabel("Poids du portefeuille")
    st.pyplot(fig))

def main():
    st.title("Approche standard de Black et Litterman")
    

    tab1, tab2 = st.tabs(["Vues", "resultat"])
    with tab1:
        st.title("Vues sur le marché")
        st.subheader('mettre dans la matrice ci dessus les vues direct ou indirect entre les différents actifs')
        vues = charger_vues()
        modifier_vues(vues)


    with tab2:
        st.title("Optimisation de black et litterman")
        black_litt()

main()