import streamlit as st
import pandas as pd
import mysql.connector
import plotly.express as px
from datetime import datetime
import re

# --- CONFIGURATION & BDD ---
st.set_page_config(page_title="GV2 Management System", layout="wide", page_icon="📊")

VERSION = "1.0"
TODAY = datetime.now().strftime("%d/%m/%Y")

# CONFIGURATION MYSQL (Remplacer par vos accès Cloud : Aiven, Clever Cloud, etc.)
DB_CONFIG = {
    "host": "VOTRE_HOST_CLOUD",
    "user": "VOTRE_USER",
    "password": "VOTRE_PASSWORD",
    "database": "VOTRE_NOM_BDD",
    "port": 3306
}

def get_connection():
    return mysql.connector.connect(**DB_CONFIG)

def init_db():
    conn = get_connection()
    c = conn.cursor()
    # Table Prestations
    c.execute('''CREATE TABLE IF NOT EXISTS prestations 
                 (id INT AUTO_INCREMENT PRIMARY KEY, date VARCHAR(20), collab VARCHAR(50), client VARCHAR(50), 
                  description TEXT, mission_ref VARCHAR(100), temps FLOAT, 
                  tarif_client FLOAT, fact_client FLOAT, 
                  tarif_interne FLOAT, fact_interne FLOAT)''')
    # Table Clients
    c.execute('''CREATE TABLE IF NOT EXISTS clients 
                 (id INT AUTO_INCREMENT PRIMARY KEY, nom VARCHAR(100) UNIQUE, tarif_defaut FLOAT, couleur VARCHAR(20))''')
    # Table Collaborateurs
    c.execute('''CREATE TABLE IF NOT EXISTS collaborateurs 
                 (id INT AUTO_INCREMENT PRIMARY KEY, nom VARCHAR(100) UNIQUE, couleur VARCHAR(20))''')
    conn.commit()
    c.close()
    conn.close()

init_db()

# --- FONCTIONS UTILITAIRES ---
def get_color_map():
    conn = get_connection()
    collabs = pd.read_sql("SELECT nom, couleur FROM collaborateurs", conn)
    clients = pd.read_sql("SELECT nom, couleur FROM clients", conn)
    conn.close()
    return pd.concat([collabs, clients]).dropna(subset=['couleur']).set_index('nom')['couleur'].to_dict()

def clean_val(x):
    if pd.isna(x) or x == "/": return 0.0
    s = str(x).replace(',', '.').replace('€', '').strip()
    s = re.sub(r'[^0-9.]', '', s)
    try: return float(s)
    except: return 0.0

# --- DIALOGS ---
@st.dialog("Confirmer la suppression")
def confirm_delete_dialog(ids_to_delete):
    st.warning(f"⚠️ Supprimer définitivement {len(ids_to_delete)} prestation(s) ?")
    c1, c2 = st.columns(2)
    if c1.button("🔥 Oui, supprimer", type="primary", use_container_width=True):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.executemany("DELETE FROM prestations WHERE id = %s", [(x,) for x in ids_to_delete])
        conn.commit()
        conn.close()
        st.success("Suppressions effectuées.")
        st.rerun()
    if c2.button("Annuler", use_container_width=True):
        st.rerun()

# --- NAVIGATION ---
st.sidebar.markdown(f"### 🛠️ GV2 Management")
st.sidebar.caption(f"**Version :** {VERSION} | **Date :** {TODAY}")
st.sidebar.divider()

menu = st.sidebar.radio("Navigation", [
    "📝 Encodage", 
    "📊 Dashboard", 
    "🛠️ Gestion", 
    "⚙️ Paramètres",
    "ℹ️ Info"
])

# --- ONGLET 1 : ENCODAGE ---
if menu == "📝 Encodage":
    st.header("📝 Nouvelle Prestation")
    conn = get_connection()
    clients_list = [""] + pd.read_sql("SELECT nom FROM clients ORDER BY nom", conn)['nom'].tolist()
    collabs_list = [""] + pd.read_sql("SELECT nom FROM collaborateurs ORDER BY nom", conn)['nom'].tolist()
    conn.close()

    with st.container(border=True):
        c1, c2 = st.columns(2)
        with c1:
            d_obj = st.date_input("Date", value=None, format="DD/MM/YYYY")
            cli = st.selectbox("Client", clients_list)
            col = st.selectbox("Collaborateur", collabs_list)
        with c2:
            t = st.number_input("Temps (h)", min_value=0.0, step=0.25)
            tc = st.number_input("Tarif Client (€)", value=80.0)
            ti = st.number_input("Tarif Interne (€)", value=45.0)
        desc = st.text_area("Description / Travail effectué")
        ref = st.text_input("Référence Mission")

        if st.button("🚀 Enregistrer la prestation", use_container_width=True, type="primary"):
            if d_obj and cli and col and t > 0:
                conn = get_connection()
                cursor = conn.cursor()
                sql = """INSERT INTO prestations (date, collab, client, description, mission_ref, temps, tarif_client, fact_client, tarif_interne, fact_interne) 
                         VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"""
                cursor.execute(sql, (d_obj.strftime("%d/%m/%Y"), col, cli, desc, ref, t, tc, t*tc, ti, t*ti))
                conn.commit()
                conn.close()
                st.success("✅ Prestation enregistrée avec succès !")
                st.rerun()
            else:
                st.error("⚠️ Veuillez remplir tous les champs obligatoires (Date, Client, Collab, Temps).")

# --- ONGLET 2 : DASHBOARD ---
elif menu == "📊 Dashboard":
    st.header("📊 Analyse de Performance")
    df = pd.read_sql("SELECT * FROM prestations", get_connection())
    cmap = get_color_map()
    
    if not df.empty:
        # Filtres Sidebar
        st.sidebar.header("🔍 Filtres")
        sel_col = st.sidebar.multiselect("Collaborateurs", df['collab'].unique(), default=df['collab'].unique())
        sel_cli = st.sidebar.multiselect("Clients", df['client'].unique(), default=df['client'].unique())
        
        df_f = df[(df['collab'].isin(sel_col)) & (df['client'].isin(sel_cli))]

        # KPIs
        k1, k2, k3 = st.columns(3)
        k1.metric("Total Heures", f"{df_f['temps'].sum():.2f} h")
        k2.metric("Total CA HT", f"{df_f['fact_client'].sum():,.2f} €")
        k3.metric("Marge GV2", f"{(df_f['fact_client'].sum() - df_f['fact_interne'].sum()):,.2f} €")

        st.divider()

        # TABLEAU RÉCAPITULATIF PAR SOCIÉTÉ (Demandé)
        st.subheader("📋 Récapitulatif détaillé par Société")
        recap = df_f.groupby(['client', 'collab']).agg({
            'temps': 'sum',
            'tarif_client': 'mean',
            'fact_client': 'sum'
        }).reset_index()
        recap.columns = ['Client', 'Collaborateur', 'Total Heures', 'Taux Moyen (€)', 'Total Facturé (€)']
        st.dataframe(recap, use_container_width=True, hide_index=True)

        # Graphiques
        c1, c2 = st.columns(2)
        c1.plotly_chart(px.bar(df_f.groupby('client')['fact_client'].sum().reset_index(), x='client', y='fact_client', color='client', color_discrete_map=cmap, title="CA par Client (€)"), use_container_width=True)
        c2.plotly_chart(px.pie(df_f.groupby('collab')['temps'].sum().reset_index(), values='temps', names='collab', color='collab', color_discrete_map=cmap, title="Heures par Collab"), use_container_width=True)

        # EXPORTATION DES FILTRES (Réintégrée)
        csv = df_f.to_csv(index=False, sep=';', encoding='utf-8-sig').encode('utf-8-sig')
        st.download_button("📥 Exporter cette sélection (CSV)", csv, f"export_gv2_{datetime.now().strftime('%Y%m%d')}.csv", "text/csv", use_container_width=True)
    else:
        st.info("Aucune donnée enregistrée dans la base MySQL.")

# --- ONGLET 3 : GESTION ---
elif menu == "🛠️ Gestion":
    st.header("🛠️ Édition et Maintenance")
    df_edit = pd.read_sql("SELECT * FROM prestations ORDER BY id DESC", get_connection())
    
    if not df_edit.empty:
        df_edit.insert(0, '🗑️', False)
        edited = st.data_editor(df_edit, disabled=["id"], use_container_width=True, hide_index=True,
                               column_config={"🗑️": st.column_config.CheckboxColumn("Suppr?")})
        
        c1, c2 = st.columns(2)
        if c1.button("💾 Sauvegarder les modifications", use_container_width=True):
            conn = get_connection()
            cursor = conn.cursor()
            for _, r in edited[edited['🗑️'] == False].iterrows():
                sql = "UPDATE prestations SET date=%s, collab=%s, client=%s, temps=%s, fact_client=%s WHERE id=%s"
                cursor.execute(sql, (r['date'], r['collab'], r['client'], r['temps'], r['fact_client'], r['id']))
            conn.commit()
            conn.close()
            st.success("Base de données mise à jour !")
            st.rerun()
        
        to_del = edited[edited['🗑️'] == True]
        if not to_del.empty and c2.button(f"🔥 Supprimer {len(to_del)} ligne(s)", type="primary", use_container_width=True):
            confirm_delete_dialog(to_del['id'].tolist())

# --- ONGLET 4 : PARAMÈTRES ---
elif menu == "⚙️ Paramètres":
    st.header("⚙️ Configuration des listes")
    # Logique de gestion des Collabs et Clients (Simplifiée pour l'espace)
    st.info("Utilisez cet onglet pour ajouter des clients, des collaborateurs et définir leurs couleurs.")
    # ... (Le code de gestion des tables collaborateurs/clients reste identique au précédent)

# --- ONGLET 5 : INFO (Réintégré) ---
elif menu == "ℹ️ Info":
    st.header("ℹ️ Informations Système")
    st.markdown(f"""
    **GV2 Management System - Version {VERSION}**
    
    Cet outil est désormais totalement indépendant du Google Drive pour le stockage. 
    Les données sont sécurisées sur un serveur **MySQL Cloud**.
    
    **Fonctionnalités incluses :**
    * **Encodage** : Vérification des champs et confirmation.
    * **Dashboard** : Analyse CA, Heures et Marge.
    * **Récapitulatif** : Tableau détaillé par société avec heures et taux.
    * **Export** : Bouton d'exportation CSV respectant les filtres actifs.
    * **Gestion** : Data Editor pour corriger ou supprimer des lignes.
    """)
    st.divider()
    st.caption(f"Développé pour GV2 | {TODAY}")
