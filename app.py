
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import pytz
import os
from streamlit_js_eval import streamlit_js_eval

st.set_page_config(page_title="Sistema de Ponto", page_icon="🕒", layout="wide")
st.title("🕒 Sistema de Registro de Ponto - Web")

# Banco de Dados
arquivo_usuarios = "usuarios.csv"
arquivo_registros = "registros.csv"

if os.path.exists(arquivo_usuarios):
    usuarios = pd.read_csv(arquivo_usuarios)
else:
    usuarios = pd.DataFrame(columns=["CPF", "Nome"])

if os.path.exists(arquivo_registros):
    registros = pd.read_csv(arquivo_registros)
else:
    registros = pd.DataFrame(columns=["CPF", "Nome", "Data", "Hora", "Tipo", "Latitude", "Longitude"])

fuso = pytz.timezone('America/Sao_Paulo')

def salvar_dados():
    usuarios.to_csv(arquivo_usuarios, index=False)
    registros.to_csv(arquivo_registros, index=False)

def obter_ultimo_registro(cpf, data):
    dados = registros[(registros['CPF'] == cpf) & (registros['Data'] == data)]
    if dados.empty:
        return None
    else:
        return dados.iloc[-1]['Tipo']

def registrar_ponto(cpf, tipo, latitude, longitude):
    nome = usuarios[usuarios['CPF'] == cpf]['Nome'].values[0]
    agora = datetime.now(fuso)
    data = agora.strftime('%d/%m/%Y')
    hora = agora.strftime('%H:%M:%S')

    ultimo = obter_ultimo_registro(cpf, data)
    regras = {
        'Entrada': ['Saída', 'Retorno', None],
        'Saída': ['Entrada', 'Retorno'],
        'Pausa': ['Entrada', 'Retorno'],
        'Retorno': ['Pausa', 'Saída']
    }
    if ultimo not in regras[tipo]:
        st.warning(f"⚠️ Batida inválida. Última batida foi '{ultimo}'. Não pode registrar '{tipo}' agora.")
        return False

    novo = pd.DataFrame([{
        "CPF": cpf,
        "Nome": nome,
        "Data": data,
        "Hora": hora,
        "Tipo": tipo,
        "Latitude": latitude,
        "Longitude": longitude
    }])

    global registros
    registros = pd.concat([registros, novo], ignore_index=True)
    salvar_dados()

    st.success(f"✅ {tipo} registrado com sucesso para {nome} às {hora} em {data}")
    return True


def calcular_horas():
    df = registros.copy()
    df['Data_Hora'] = pd.to_datetime(df['Data'] + ' ' + df['Hora'], format='%d/%m/%Y %H:%M:%S')
    df = df.sort_values(by=['CPF', 'Data_Hora'])

    resultado = []

    for (cpf, data), grupo in df.groupby(['CPF', 'Data']):
        entrada = None
        total = timedelta()

        for _, linha in grupo.iterrows():
            tipo = linha['Tipo']
            data_hora = linha['Data_Hora']

            if tipo == 'Entrada':
                entrada = data_hora
            elif tipo == 'Saída' and entrada:
                total += data_hora - entrada
                entrada = None
            elif tipo == 'Pausa' and entrada:
                total += data_hora - entrada
                entrada = None
            elif tipo == 'Retorno':
                entrada = data_hora

        nome = grupo['Nome'].iloc[0]
        horas_trabalhadas = round(total.total_seconds() / 3600, 2)

        resultado.append({
            "CPF": cpf,
            "Nome": nome,
            "Data": data,
            "Horas Trabalhadas": horas_trabalhadas
        })

    return pd.DataFrame(resultado)


def calcular_banco(jornada=8):
    horas = calcular_horas()
    horas["Saldo do Dia"] = horas["Horas Trabalhadas"] - jornada
    banco = horas.groupby("CPF").agg({"Saldo do Dia": "sum"}).reset_index()
    banco = banco.merge(usuarios, on="CPF")
    banco["Saldo Acumulado"] = banco["Saldo do Dia"].round(2)
    banco = banco[["CPF", "Nome", "Saldo Acumulado"]]
    return banco


st.sidebar.subheader("🧑‍💼 Login ou Cadastro")
cpf = st.sidebar.text_input("CPF", max_chars=11)
nome = st.sidebar.text_input("Nome")

if cpf and nome:
    if cpf not in usuarios['CPF'].values:
        st.sidebar.success("Novo usuário cadastrado.")
        usuarios = pd.concat([usuarios, pd.DataFrame([{"CPF": cpf, "Nome": nome}])], ignore_index=True)
        salvar_dados()
    else:
        st.sidebar.info(f"Bem-vindo(a) {nome}!")

    st.sidebar.subheader("📍 Localização (Puxada automática)")

    loc = streamlit_js_eval(
        js_expressions="navigator.geolocation.getCurrentPosition((pos) => {return {latitude: pos.coords.latitude, longitude: pos.coords.longitude};})",
        key="getGeoLocation"
    )
    
    if loc and isinstance(loc, dict):
        latitude = str(loc.get("latitude", ""))
        longitude = str(loc.get("longitude", ""))
        st.sidebar.success(f"📍 Localização capturada")
    else:
        latitude = ""
        longitude = ""
        st.sidebar.warning("⚠️ Permita o acesso à sua localização no navegador!")

    st.sidebar.write(f"Latitude: {latitude}")
    st.sidebar.write(f"Longitude: {longitude}")

    st.subheader("Registrar Ponto")
    tipo = st.selectbox("Tipo de Ponto", ["Entrada", "Saída", "Pausa", "Retorno"])

    if st.button("📲 Registrar Ponto"):
        if latitude and longitude:
            registrar_ponto(cpf, tipo, latitude, longitude)
        else:
            st.warning("⚠️ A localização não foi capturada. Verifique se você permitiu o acesso no navegador.")

    st.subheader("📑 Relatórios")
    aba = st.radio("Escolha uma opção", ["Espelho de Ponto", "Horas Trabalhadas", "Banco de Horas"])

    if aba == "Espelho de Ponto":
        st.dataframe(registros)
    elif aba == "Horas Trabalhadas":
        st.dataframe(calcular_horas())
    elif aba == "Banco de Horas":
        st.dataframe(calcular_banco())

    with st.expander("⬇️ Baixar Relatório Excel"):
        registros.to_excel("registros.xlsx", index=False)
        with open("registros.xlsx", "rb") as file:
            st.download_button("Baixar Espelho de Ponto", file, "registros.xlsx")

else:
    st.info("Informe seu CPF e Nome para começar.")
