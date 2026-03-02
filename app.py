import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
from datetime import datetime
import os

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

init_db()

def get_dynamic_colors():
    conn = get_connection()
    c_df = pd.read_sql("SELECT nom, couleur FROM collaborateurs", conn)
    l_df = pd.read_sql("SELECT nom, couleur FROM clients", conn)
    db_colors = pd.concat([c_df, l_df]).set_index('nom')['couleur'].to_dict()
    return {**db_colors, **FORCED_COLORS}

# --- DIALOGUE DE CONFIRMATION DE SUPPRESSION ---
@st.dialog("Confirmer la suppression")
def confirm_delete_dialog(ids_to_delete):
    st.warning(f"⚠️ Êtes-vous sûr de vouloir supprimer définitivement {len(ids_to_delete)} prestation(s) ?")
    st.write("Cette action est irréversible.")
    c1, c2 = st.columns(2)
    if c1.button("🔥 Oui, supprimer", type="primary", use_container_width=True):
        conn = get_connection()
        cursor = conn.cursor()
        query = f"DELETE FROM prestations WHERE id IN ({','.join(['?']*len(ids_to_delete))})"
        cursor.execute(query, ids_to_delete)
        conn.commit()
        conn.close()
        st.success("Suppression réussie !")
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
                conn.execute("INSERT INTO prestations (date, collab, client, description, mission_ref, temps, tarif_client, fact_client, tarif_interne, fact_interne) VALUES (?,?,?,?,?,?,?,?,?,?)", 
                             (d.strftime("%d/%m/%Y"), col, cli, desc, ref, t, tc, t*tc, ti, t*ti))
                conn.commit(); st.success("Ok !"); st.balloons()

# --- 2. DASHBOARD ---
elif menu == "📊 Dashboard":
    st.header("📊 Dashboard d'Analyse")
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

            # --- TABLEAU RÉCAPITULATIF PAR SOCIÉTÉ ---
            st.subheader("📋 Récapitulatif par Société / Collab")
            recap = df_f.groupby(['client', 'collab']).agg({'temps': 'sum', 'fact_client': 'sum', 'fact_interne': 'sum'}).reset_index()
            recap['Marge (€)'] = recap['fact_client'] - recap['fact_interne']
            st.dataframe(recap, use_container_width=True, hide_index=True)

            # Exportation CSV des filtres
            csv = df_f.to_csv(index=False, sep=';', encoding='utf-8-sig')
            st.download_button("📥 Exporter cette sélection (CSV)", csv, "export_filtre.csv", "text/csv")
        else: st.warning("Aucune donnée pour ces filtres.")
    else: st.info("Base vide.")

# --- 3. GESTION (SUPPRESSION CORRIGÉE) ---
elif menu == "🛠️ Gestion":
    st.header("🛠️ Gestion & Suppression")
    conn = get_connection()
    df_g = pd.read_sql("SELECT * FROM prestations ORDER BY id DESC", conn)
    
    if not df_g.empty:
        # Ajout d'une colonne de sélection pour la suppression
        df_g.insert(0, "Sélection", False)
        
        st.info("Cochez les cases 'Sélection' pour supprimer des lignes ou modifiez directement les cellules pour mettre à jour.")
        edited_df = st.data_editor(df_g, use_container_width=True, hide_index=True, disabled=["id"])
        
        col_save, col_del = st.columns([1, 1])
        
        if col_save.button("💾 Sauvegarder les modifications", use_container_width=True):
            # On retire la colonne temporaire de sélection avant sauvegarde
            df_to_save = edited_df.drop(columns=["Sélection"])
            df_to_save.to_sql('prestations', conn, if_exists='replace', index=False)
            st.success("Données mises à jour !"); st.rerun()
            
        # Logique de suppression
        to_delete = edited_df[edited_df["Sélection"] == True]
        if not to_delete.empty:
            if col_del.button(f"🗑️ Supprimer {len(to_delete)} ligne(s)", type="primary", use_container_width=True):
                confirm_delete_dialog(to_delete['id'].tolist())
    else:
        st.info("Aucune donnée à gérer.")

# --- 4. PARAMÈTRES ---
elif menu == "⚙️ Paramètres":
    st.header("⚙️ Paramètres")
    conn = get_connection()
    t_maint, t_lists = st.tabs(["💾 Maintenance", "👥 Listes & Couleurs"])
    
    with t_maint:
        if os.path.exists(DB_PATH):
            with open(DB_PATH, "rb") as f: st.download_button("📥 Télécharger Backup .db", f, "gv2_backup.db")
    
    with t_lists:
        col1, col2 = st.columns(2)
        for i, (title, table) in enumerate([("Collaborateurs", "collaborateurs"), ("Clients", "clients")]):
            with [col1, col2][i]:
                st.subheader(title)
                with st.form(f"add_{table}", clear_on_submit=True):
                    name = st.text_input(f"Nom {title[:-1]}")
                    if st.form_submit_button("Ajouter"):
                        if name: conn.execute(f"INSERT OR IGNORE INTO {table} (nom, couleur) VALUES (?,?)", (name.strip(), "#3498db")); conn.commit(); st.rerun()
                # Affichage avec suppression individuelle
                for r in conn.execute(f"SELECT id, nom FROM {table}").fetchall():
                    c = st.columns([3, 1])
                    c[0].write(r[1])
                    if c[1].button("🗑️", key=f"del_{table}_{r[0]}"):
                        conn.execute(f"DELETE FROM {table} WHERE id=?", (r[0],)); conn.commit(); st.rerun()

# --- 5. INFO ---
elif menu == "ℹ️ Info":
    st.header("ℹ️ Informations Système")
    st.markdown(f"""
    **GV2 Management System - Version {VERSION}**
    
    ### Fonctionnalités :
    * **📝 Encodage** : Enregistrement des prestations avec calcul automatique de la facturation.
    * **📊 Dashboard** : Analyse visuelle avec filtres croisés (Date, Collab, Client).
    * **🛠️ Gestion** : Modification en direct des données et suppression sécurisée avec message de confirmation.
    * **⚙️ Paramètres** : Gestion des bases de données et des listes déroulantes.
    * **📥 Export** : Extraction des données filtrées au format CSV pour Excel.
    
    *Développé pour une gestion simplifiée et sécurisée.*
    """)
