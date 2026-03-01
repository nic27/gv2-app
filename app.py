import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
from datetime import datetime
import os

# --- CONFIGURATION & BDD ---
st.set_page_config(page_title="GV2 Management System", layout="wide", page_icon="📊")

VERSION = "1.0"
DATE_FILE = datetime.now().strftime("%d_%m_%Y")
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
    # Structure exacte attendue par le système
    c.execute('''CREATE TABLE IF NOT EXISTS prestations 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, collab TEXT, client TEXT, 
                  description TEXT, mission_ref TEXT, temps REAL, 
                  tarif_client REAL, fact_client REAL, 
                  tarif_interne REAL, fact_interne REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS clients (id INTEGER PRIMARY KEY, nom TEXT UNIQUE, couleur TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS collaborateurs (id INTEGER PRIMARY KEY, nom TEXT UNIQUE, couleur TEXT)''')
    conn.commit()

init_db()

# --- FONCTIONS UTILITAIRES ---
def get_dynamic_colors():
    conn = get_connection()
    c_df = pd.read_sql("SELECT nom, couleur FROM collaborateurs", conn)
    l_df = pd.read_sql("SELECT nom, couleur FROM clients", conn)
    db_colors = pd.concat([c_df, l_df]).set_index('nom')['couleur'].to_dict()
    return {**FORCED_COLORS, **db_colors}

@st.dialog("⚠️ RESTAURATION")
def confirm_restore_dialog(uploaded_file):
    st.error("### ATTENTION : ÉCRASEMENT DES DONNÉES")
    if st.button("🔥 CONFIRMER LA RESTAURATION", type="primary", use_container_width=True):
        with open(DB_PATH, "wb") as f:
            f.write(uploaded_file.getbuffer())
        st.success("Base restaurée !"); st.rerun()

# --- BARRE LATÉRALE ---
if os.path.exists("logo_gv2.png"):
    st.sidebar.image("logo_gv2.png", use_container_width=True)
st.sidebar.markdown(f"### 🛠️ GV2 Management")
st.sidebar.caption(f"**Version :** {VERSION}")
menu = st.sidebar.radio("Navigation", ["📝 Encodage", "📊 Dashboard", "🛠️ Gestion", "⚙️ Paramètres", "ℹ️ Aide & Infos"])

# --- DASHBOARD ---
if menu == "📊 Dashboard":
    st.header("📊 Dashboard")
    df = pd.read_sql("SELECT * FROM prestations", get_connection())
    if not df.empty:
        df['date_dt'] = pd.to_datetime(df['date'].str.replace('-', '/'), format='%d/%m/%Y', dayfirst=True, errors='coerce')
        df = df.dropna(subset=['date_dt'])
        df['Mois_Label'] = df['date_dt'].dt.strftime('%m/%Y')
        
        y_list = sorted(df['date_dt'].dt.year.unique(), reverse=True)
        sel_y = st.sidebar.multiselect("Années", y_list, default=y_list)
        
        mois_options = sorted(df[df['date_dt'].dt.year.isin(sel_y)]['Mois_Label'].unique(), reverse=True)
        sel_m = st.sidebar.multiselect("Mois", mois_options, default=mois_options)
        
        df_f = df[(df['date_dt'].dt.year.isin(sel_y)) & (df['Mois_Label'].isin(sel_m))]
        
        if not df_f.empty:
            k1, k2, k3 = st.columns(3)
            k1.metric("Heures", f"{df_f['temps'].sum():.2f} h")
            k2.metric("CA HT", f"{df_f['fact_client'].sum():,.2f} €")
            k3.metric("Marge", f"{(df_f['fact_client'].sum() - df_f['fact_interne'].sum()):,.2f} €")
            st.plotly_chart(px.bar(df_f.groupby('client')['fact_client'].sum().reset_index(), x='client', y='fact_client', color='client', color_discrete_map=get_dynamic_colors()), use_container_width=True)
    else: st.info("Base vide.")

# --- PARAMÈTRES (FIX IMPORT) ---
elif menu == "⚙️ Paramètres":
    st.header("⚙️ Configuration")
    conn = get_connection()
    t_maint, t_lists, t_csv = st.tabs(["💾 Maintenance", "👥 Collaborateurs & Clients", "📥 Import CSV"])
    
    with t_maint:
        c1, c2 = st.columns(2)
        with c1:
            if os.path.exists(DB_PATH):
                with open(DB_PATH, "rb") as f:
                    st.download_button(f"📥 Backup_{DATE_FILE}.db", f, f"backup_gv2_{DATE_FILE}.db", use_container_width=True)
        with c2:
            up_db = st.file_uploader("Restaurer .db", type="db")
            if up_db and st.button("🚀 Lancer"): confirm_restore_dialog(up_db)

    with t_lists:
        col1, col2 = st.columns(2)
        for i, (title, table) in enumerate([("👥 Collaborateurs", "collaborateurs"), ("🏢 Clients", "clients")]):
            with [col1, col2][i]:
                st.subheader(title)
                with st.form(f"add_{table}", clear_on_submit=True):
                    n = st.text_input(f"Nouveau {title[:-1]}")
                    if st.form_submit_button("Ajouter"):
                        if n: conn.execute(f"INSERT OR IGNORE INTO {table} (nom, couleur) VALUES (?,?)", (n.strip(), "#3498db" if i==0 else "#e67e22")); conn.commit(); st.rerun()
                for r in conn.execute(f"SELECT id, nom, couleur FROM {table} ORDER BY nom").fetchall():
                    cols = st.columns([3, 1, 1])
                    cols[0].write(r[1])
                    nc = cols[1].color_picker("Col", r[2], key=f"p_{table}_{r[0]}", label_visibility="collapsed")
                    if nc != r[2]: conn.execute(f"UPDATE {table} SET couleur=? WHERE id=?", (nc, r[0])); conn.commit(); st.rerun()
                    if cols[2].button("🗑️", key=f"d_{table}_{r[0]}"): conn.execute(f"DELETE FROM {table} WHERE id=?", (r[0],)); conn.commit(); st.rerun()

    with t_csv:
        st.subheader("📥 Import CSV (Sécurisé)")
        up_csv = st.file_uploader("Fichier CSV (Séparateur ;)", type="csv")
        if up_csv:
            df_raw = pd.read_csv(up_csv, sep=';', engine='python')
            
            # 1. Mapping rigoureux
            mapping = {
                'date': 'Date', 'collab': 'collab', 'client': 'Nom du client',
                'description': 'Description', 'mission_ref': 'Référence de mission',
                'temps': 'Temps de travail', 'tarif_client': 'Tarif horaire client',
                'fact_client': 'Facturation horaire client',
                'tarif_interne': 'Tarif horaire interne GV2',
                'fact_interne': 'Facturation interne GV2'
            }
            
            # On cherche les colonnes présentes
            found_cols = {v: k for k, v in mapping.items() if v in df_raw.columns}
            df_imp = df_raw[list(found_cols.keys())].rename(columns=found_cols)

            # 2. Nettoyage des données (IMPORTANT pour éviter sqlite3.Error)
            if 'date' in df_imp.columns:
                df_imp['date'] = df_imp['date'].astype(str).str.replace('-', '/')
            
            for col in ['temps', 'tarif_client', 'fact_client', 'tarif_interne', 'fact_interne']:
                if col in df_imp.columns:
                    # Retire les €, les espaces insécables et remplace la virgule par un point
                    df_imp[col] = df_imp[col].astype(str).str.replace('€', '').str.replace(',', '.').str.replace('\xa0', '').str.strip()
                    df_imp[col] = pd.to_numeric(df_imp[col], errors='coerce').fillna(0)

            st.write("Données filtrées prêtes pour la base de données :")
            st.dataframe(df_imp.head(3))
            
            if st.button("✅ Lancer l'importation"):
                try:
                    # On ne garde QUE les colonnes qui existent physiquement dans la table SQLite
                    cols_db = ['date', 'collab', 'client', 'description', 'mission_ref', 'temps', 'tarif_client', 'fact_client', 'tarif_interne', 'fact_interne']
                    df_final = df_imp[[c for c in cols_db if c in df_imp.columns]]
                    
                    df_final.to_sql('prestations', conn, if_exists='append', index=False)
                    st.success(f"🎉 Importation réussie : {len(df_final)} lignes ajoutées !")
                    st.balloons()
                except Exception as e:
                    st.error(f"Erreur d'importation : {e}")

# --- RESTES (Encodage, Gestion, Aide) ---
elif menu == "📝 Encodage": st.write("Utilisez les Paramètres pour configurer vos listes.")
elif menu == "🛠️ Gestion": st.dataframe(pd.read_sql("SELECT * FROM prestations ORDER BY id DESC", get_connection()))
elif menu == "ℹ️ Aide & Infos": st.write(f"GV2 System v{VERSION}")
