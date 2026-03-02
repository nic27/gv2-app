import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
from datetime import datetime
import os
import re

# --- CONFIGURATION & BDD ---
st.set_page_config(page_title="GV2 Management System", layout="wide", page_icon="📊")

VERSION = "1.0"
DB_PATH = 'gv2_data.db'

FORCED_COLORS = {
    "JC": "#E22F2F", "Ludo": "#2A33C3", "Nico": "#20DC46",
    "Skydiving Promotion": "#161515", "Sourse": "#C03BD6", "Stemme Belgium": "#999999"
}

def get_connection():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    conn = get_connection()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS prestations 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, collab TEXT, client TEXT, 
                  description TEXT, mission_ref TEXT, temps REAL, 
                  tarif_client REAL, fact_client REAL, 
                  tarif_interne REAL, fact_interne REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS clients (id INTEGER PRIMARY KEY, nom TEXT UNIQUE, couleur TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS collaborateurs (id INTEGER PRIMARY KEY, nom TEXT UNIQUE, couleur TEXT)''')
    conn.commit()
    conn.close()

init_db()

def get_dynamic_colors():
    conn = get_connection()
    c_df = pd.read_sql("SELECT nom, couleur FROM collaborateurs", conn)
    l_df = pd.read_sql("SELECT nom, couleur FROM clients", conn)
    conn.close()
    db_colors = pd.concat([c_df, l_df]).set_index('nom')['couleur'].to_dict()
    return {**db_colors, **FORCED_COLORS}

# --- DIALOGUES DE SÉCURITÉ ---
@st.dialog("⚠️ CONFIRMER L'IMPORTATION DB")
def confirm_db_restore(uploaded_file):
    st.warning("🚨 ATTENTION : L'importation d'une base de données écrasera l'intégralité de vos prestations actuelles, vos clients et vos collaborateurs.")
    st.error("Cette action est irréversible. Assurez-vous d'avoir une sauvegarde.")
    if st.button("🔥 ÉCRASER ET RESTAURER", use_container_width=True, type="primary"):
        with open(DB_PATH, "wb") as f:
            f.write(uploaded_file.getbuffer())
        st.success("Base de données restaurée avec succès !")
        st.rerun()

@st.dialog("Confirmer la suppression")
def confirm_delete_dialog(ids_to_delete):
    st.warning(f"⚠️ Voulez-vous supprimer définitivement ces {len(ids_to_delete)} ligne(s) ?")
    c1, c2 = st.columns(2)
    if c1.button("🔥 Oui, supprimer", type="primary", use_container_width=True):
        conn = get_connection()
        cursor = conn.cursor()
        query = f"DELETE FROM prestations WHERE id IN ({','.join(['?']*len(ids_to_delete))})"
        cursor.execute(query, ids_to_delete)
        conn.commit()
        conn.close()
        st.success("Suppression effectuée.")
        st.rerun()
    if c2.button("Annuler", use_container_width=True):
        st.rerun()

# --- NAVIGATION ---
st.sidebar.markdown(f"### 🛠️ GV2 Management")
st.sidebar.caption(f"**Version :** {VERSION}")
menu = st.sidebar.radio("Navigation", ["📝 Encodage", "📊 Dashboard", "🛠️ Gestion", "⚙️ Paramètres", "ℹ️ Info"])

# --- 1. ENCODAGE ---
if menu == "📝 Encodage":
    st.header("📝 Nouvel Encodage")
    conn = get_connection()
    collabs = [""] + pd.read_sql("SELECT nom FROM collaborateurs ORDER BY nom", conn)['nom'].tolist()
    clients = [""] + pd.read_sql("SELECT nom FROM clients ORDER BY nom", conn)['nom'].tolist()
    conn.close()
    
    with st.form("f_enc", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            d = st.date_input("Date")
            cli = st.selectbox("Client", clients)
            col = st.selectbox("Collaborateur", collabs)
            ref = st.text_input("Référence Mission")
        with c2:
            t = st.number_input("Temps (h)", value=0.0, step=0.25)
            tc = st.number_input("Tarif Client (€)", value=0.0)
            ti = st.number_input("Tarif Interne (€)", value=0.0)
        desc = st.text_area("Description")
        if st.form_submit_button("🚀 ENREGISTRER"):
            if cli and col and t > 0:
                conn = get_connection()
                conn.execute("INSERT INTO prestations (date, collab, client, description, mission_ref, temps, tarif_client, fact_client, tarif_interne, fact_interne) VALUES (?,?,?,?,?,?,?,?,?,?)", 
                             (d.strftime("%d/%m/%Y"), col, cli, desc, ref, t, tc, t*tc, ti, t*ti))
                conn.commit(); conn.close()
                st.success("Enregistré !"); st.balloons()

# --- 2. DASHBOARD ---
elif menu == "📊 Dashboard":
    st.header("📊 Dashboard")
    df = pd.read_sql("SELECT * FROM prestations", get_connection())
    if not df.empty:
        df['date_dt'] = pd.to_datetime(df['date'], format='%d/%m/%Y', dayfirst=True, errors='coerce')
        df = df.dropna(subset=['date_dt'])
        df['Année'] = df['date_dt'].dt.year
        df['Mois_Label'] = df['date_dt'].dt.strftime('%m/%Y')
        df['Mois_Tri'] = df['date_dt'].dt.strftime('%Y-%m')

        st.sidebar.header("🔍 Filtres")
        sel_y = st.sidebar.multiselect("Années", sorted(df['Année'].unique(), reverse=True), default=df['Année'].unique())
        mask_y = df[df['Année'].isin(sel_y)]
        available_months = mask_y.sort_values('Mois_Tri', ascending=False)['Mois_Label'].unique().tolist()
        sel_m = st.sidebar.multiselect("Mois", available_months, default=available_months)
        sel_co = st.sidebar.multiselect("Collaborateurs", sorted(df['collab'].unique()), default=df['collab'].unique())
        sel_cl = st.sidebar.multiselect("Clients", sorted(df['client'].unique()), default=df['client'].unique())
        
        df_f = df[(df['Année'].isin(sel_y)) & (df['Mois_Label'].isin(sel_m)) & (df['collab'].isin(sel_co)) & (df['client'].isin(sel_cl))]
        
        if not df_f.empty:
            k1, k2, k3 = st.columns(3)
            k1.metric("Heures", f"{df_f['temps'].sum():.1f}h")
            k2.metric("CA HT", f"{df_f['fact_client'].sum():,.2f} €")
            k3.metric("Marge", f"{(df_f['fact_client'].sum() - df_f['fact_interne'].sum()):,.2f} €")
            
            st.plotly_chart(px.bar(df_f.groupby('client')['fact_client'].sum().reset_index(), x='client', y='fact_client', color='client', color_discrete_map=get_dynamic_colors()), use_container_width=True)

            st.subheader("📋 Récapitulatif par Société")
            recap = df_f.groupby(['client', 'collab']).agg({'temps': 'sum', 'fact_client': 'sum'}).reset_index()
            st.dataframe(recap, use_container_width=True, hide_index=True)

            csv = df_f.to_csv(index=False, sep=';', encoding='utf-8-sig')
            st.download_button("📥 Exporter la sélection (CSV)", csv, "export_gv2.csv", "text/csv")
    else: st.info("Base vide.")

# --- 3. GESTION ---
elif menu == "🛠️ Gestion":
    st.header("🛠️ Gestion des prestations")
    conn = get_connection()
    df_g = pd.read_sql("SELECT * FROM prestations ORDER BY id DESC", conn)
    
    if not df_g.empty:
        df_g.insert(0, "Sélection", False)
        edited_df = st.data_editor(df_g, use_container_width=True, hide_index=True, disabled=["id"])
        
        c1, c2 = st.columns(2)
        if c1.button("💾 Sauvegarder modifications", use_container_width=True):
            df_to_save = edited_df.drop(columns=["Sélection"])
            df_to_save.to_sql('prestations', conn, if_exists='replace', index=False)
            st.success("Mis à jour !"); st.rerun()
            
        to_del = edited_df[edited_df["Sélection"] == True]
        if not to_del.empty and c2.button(f"🗑️ Supprimer {len(to_del)} ligne(s)", type="primary", use_container_width=True):
            confirm_delete_dialog(to_del['id'].tolist())
    conn.close()

# --- 4. PARAMÈTRES ---
elif menu == "⚙️ Paramètres":
    st.header("⚙️ Paramètres")
    t_maint, t_csv = st.tabs(["💾 Base de données", "📥 Import CSV"])
    
    with t_maint:
        st.subheader("Sauvegarde et Restauration")
        if os.path.exists(DB_PATH):
            with open(DB_PATH, "rb") as f:
                st.download_button("📥 Télécharger Backup .db", f, "gv2_data.db")
        
        st.divider()
        up_db = st.file_uploader("Importer un fichier gv2_data.db", type="db")
        if up_db:
            if st.button("🚀 Lancer l'importation DB"):
                confirm_db_restore(up_db)

    with t_csv:
        st.subheader("Importation CSV")
        st.info("Le CSV doit utiliser le point-virgule (;) comme séparateur.")
        up_csv = st.file_uploader("Fichier CSV", type="csv")
        if up_csv:
            if st.button("✅ Valider l'importation CSV"):
                try:
                    df_imp = pd.read_csv(up_csv, sep=';', engine='python')
                    # Nettoyage des colonnes numériques
                    for col in ['temps', 'tarif_client', 'fact_client', 'tarif_interne', 'fact_interne']:
                        if col in df_imp.columns:
                            df_imp[col] = df_imp[col].astype(str).str.replace(',', '.').str.replace('€', '').str.strip()
                            df_imp[col] = pd.to_numeric(df_imp[col], errors='coerce').fillna(0)
                    
                    conn = get_connection()
                    # Ajout auto des nouveaux clients/collabs pour éviter les listes vides
                    if 'collab' in df_imp.columns:
                        for c in df_imp['collab'].unique():
                            conn.execute("INSERT OR IGNORE INTO collaborateurs (nom, couleur) VALUES (?,?)", (str(c), "#3498db"))
                    if 'client' in df_imp.columns:
                        for cl in df_imp['client'].unique():
                            conn.execute("INSERT OR IGNORE INTO clients (nom, couleur) VALUES (?,?)", (str(cl), "#e67e22"))
                    
                    df_imp.to_sql('prestations', conn, if_exists='append', index=False)
                    conn.commit(); conn.close()
                    st.success("Importation CSV réussie !")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erreur lors de l'import : {e}")

# --- 5. INFO ---
elif menu == "ℹ️ Info":
    st.header("ℹ️ Aide & Info")
    st.markdown(f"""
    **Système de gestion GV2 Management v{VERSION}**
    
    * **Dashboard** : Filtrage dynamique par Année, Mois, Collab et Client. L'exportation respecte vos filtres.
    * **Gestion** : Cochez la case à gauche pour activer le bouton de suppression groupée.
    * **Paramètres** : 
        * **DB** : Permet de sauvegarder ou de restaurer l'intégralité du système.
        * **CSV** : Permet d'ajouter des prestations en masse.
    """)
