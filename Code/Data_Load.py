import pandas as pd
import streamlit as st
import yfinance as yf
from pathlib import Path
from datetime import date

def dernier_close(ticker: str):
    if not ticker:
        return None
    data = yf.download(ticker, period="1d", interval="1d", progress=False)
    if data.empty:
        return None
    return float(data["Close"].iloc[-1])

def ticker():
    path = Path("Data/Tickers.csv")
    tickers = pd.read_csv(path, sep=";")

    # --- Ajout ---
    new_ticker = st.text_input("Entrer un nouveau ticker :", value="", max_chars=10, key="new_ticker_input")

    if new_ticker:
        test = dernier_close(new_ticker)
        if test is None:
            st.write("Le ticker entré n'est pas valide.")
        else:
            if new_ticker not in tickers["Tickers"].values:
                tickers.loc[len(tickers)] = [new_ticker]
                tickers.to_csv(path, index=False)
                st.write(f"Ticker ajouté : {new_ticker}")
            else:
                st.write("Le ticker est déjà dans la liste.")

    # --- Suppression ---
    st.subheader("Supprimer un ticker")
    selected = st.selectbox("Sélectionner un ticker à retirer :", tickers["Tickers"])
    if st.button("Supprimer",key='suppression'):
        tickers = tickers[tickers["Tickers"] != selected]
        tickers.to_csv(path, index=False)
        st.write(f"Ticker supprimé : {selected}")
    st.subheader("Liste des tickers")
    st.dataframe(tickers, use_container_width=True)

    if st.button("Enregistrer les changements",key='enregistrement'):
        tickers.to_csv("Data/Tickers.csv",sep=';',index=False)
        st.write('La Novelle liste de tickers est bien enregistrée !!')
        
def Interpolation (df):
    df = df.sort_index()  
    cols_with_nan = df.columns[df.isna().any()].tolist()
    df = df.interpolate(method='linear').ffill().bfill()
    if cols_with_nan:
        st.warning(f"Une interpolation de prix a été effectuée pour : {', '.join(cols_with_nan)}")
    return df

def Actualisation_DB():
    Date_bebut = date(2015, 10, 8)
    Fin = date.today()

    path = Path("Data/Data_Set_daily.csv")
    Data = pd.read_csv(path, sep=";")
    
    path2 = Path("Data/Tickers.csv")
    tickers = pd.read_csv(path2, sep=";")
    tickers_in = Data.columns
    tickers_out = tickers[~tickers['Tickers'].isin(tickers_in)]
    tickers_out = tickers_out['Tickers'].dropna().tolist()
    
    
    st.table(tickers_out)
    Date_Max = Data.index.max()
    if tickers_in is not None and Date_Max != date.today():
        Ancien_tickers = yf.download(
            tickers=tickers_in,
            start=Date_Max,
            end=Fin,
            interval="1d",
            progress=False
        )
        close_ancien = Ancien_tickers["Close"]   
        Data = pd.concat([Data,close_ancien],axis=1)
    if tickers_out is not None:
        new_data = yf.download(
            tickers=tickers_out,
            start=Date_bebut,
            end=Fin,
            interval="1d",
            progress=False
        )
        close = new_data["Close"]
        Data = pd.merge(Data, close, how='outer', left_index=True, right_index=True)
    Data = Data[Data.index != 0]
    Data=Interpolation(Data)
    Data.to_csv(path,sep=';')

def Base_Daily():
    if st.button("Enregistrer les changements",key='actualisation DB'):
        Actualisation_DB()

def main():
    st.title("Gestion des bases de données")
    tab1, tab2 = st.tabs(["Tickers", "Base Daily"])
    with tab1:
        st.title("Gestion des tikers")
        ticker()

    with tab2:
        st.title("Base de données Daily")
        Base_Daily()

main()