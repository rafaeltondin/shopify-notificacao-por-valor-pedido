import requests
from datetime import datetime, timedelta
import pytz
import re
import traceback
import logging
import sys
import random
import time
import schedule
import json
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from dotenv import load_dotenv
import os

# Carregar variáveis de ambiente do arquivo .env
load_dotenv()

# Configuração de logging
logging.basicConfig(filename='recompensas.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configurações da API Shopify
SHOP_NAME = os.getenv('SHOP_NAME')
ACCESS_TOKEN = os.getenv('ACCESS_TOKEN')

# Configurações da API Evolution
EVOLUTION_ENDPOINT = os.getenv('EVOLUTION_ENDPOINT')
EVOLUTION_INSTANCE = os.getenv('EVOLUTION_INSTANCE')
EVOLUTION_API_KEY = os.getenv('EVOLUTION_API_KEY')

# URL base da loja
SHOP_URL = os.getenv('SHOP_URL')

# Arquivo para armazenar mensagens enviadas
MENSAGENS_ENVIADAS_FILE = "mensagens_enviadas.json"

# Configuração de retry para requisições HTTP
def requests_retry_session(
    retries=3,
    backoff_factor=0.3,
    status_forcelist=(500, 502, 504),
    session=None,
):
    session = session or requests.Session()
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

class SistemaRecompensas:
    def __init__(self):
        self.faixas_orcamento = [500, 1000, 2000, 5000]
        self.descontos = [5, 10, 15, 20]
        self.mensagens_enviadas = self.carregar_mensagens_enviadas()
        logger.info("Sistema de Recompensas inicializado.")

        # Verificar conexão com Shopify
        if self.verificar_conexao_shopify():
            logger.info("Conexão com Shopify estabelecida com sucesso.")
        else:
            logger.error("Falha ao conectar com Shopify. Verifique suas credenciais.")

    def verificar_conexao_shopify(self):
        try:
            session = requests_retry_session()
            response = session.get(
                f"https://{SHOP_NAME}/admin/api/2023-01/shop.json",
                headers={"X-Shopify-Access-Token": ACCESS_TOKEN}
            )
            response.raise_for_status()
            return True
        except requests.RequestException as e:
            logger.error(f"Erro ao conectar com Shopify: {str(e)}")
            return False

    def calcular_desconto(self, total_gasto):
        logger.info(f"Calculando desconto para total gasto: R${total_gasto:.2f}")
        for i, faixa in enumerate(reversed(self.faixas_orcamento)):
            if total_gasto >= faixa:
                desconto = self.descontos[-(i+1)]
                logger.info(f"Desconto de {desconto}% aplicado (faixa de R${faixa}).")
                return desconto, str(faixa)
        logger.info("Nenhum desconto aplicado.")
        return 0, "0"

    def gerar_oferta(self, cliente_id, nome, telefone, total_gasto):
        logger.info(f"Gerando oferta para {nome} (ID: {cliente_id})...")
        desconto, faixa = self.calcular_desconto(total_gasto)
        
        if cliente_id in self.mensagens_enviadas:
            logger.info(f"Oferta já enviada para o cliente {nome} (ID: {cliente_id}).")
            return None

        if desconto > 0:
            logger.info(f"Criando cupom Shopify para {nome}...")
            cupom_info = criar_cupom_shopify(nome, telefone, total_gasto)
            if cupom_info:
                url_desconto = f"{SHOP_URL}/discount/{cupom_info['codigo']}"
                oferta = (f"Prezado(a) {nome.split()[0]},\n\n"
                          f"A Fiber agradece por você já ter batido R${faixa} em compras conosco. "
                          f"Como forma de reconhecimento pela sua fidelidade, gostaríamos de oferecer "
                          f"um desconto especial de {cupom_info['desconto']}% em sua próxima compra.\n\n"
                          f"Para usufruir deste desconto, por favor, utilize o seguinte link: "
                          f"{url_desconto}\n\n"
                          f"Informamos que esta oferta é válida até {cupom_info['validade']}. "
                          f"Recomendamos que aproveite esta oportunidade o quanto antes.\n\n"
                          f"Agradecemos por escolher a Fiber e esperamos continuar atendendo suas "
                          f"necessidades em produtos esportivos de alta qualidade.\n\n"
                          f"Atenciosamente,\n"
                          f"Equipe Fiber\n\n"
                          f"⚠️ Este número de WhatsApp é apenas para notificações sobre ofertas. "
                          f"Para dúvidas ou suporte, por favor, utilize o número: 5199692122")
                
                self.mensagens_enviadas[cliente_id] = datetime.now().isoformat()
                self.salvar_mensagens_enviadas()
                logger.info(f"Oferta gerada com sucesso para {nome}.")
                return oferta
        else:
            logger.info(f"Nenhuma oferta gerada para {nome} (desconto = 0%).")
        return None

    def carregar_mensagens_enviadas(self):
        try:
            with open(MENSAGENS_ENVIADAS_FILE, 'r') as f:
                mensagens = json.load(f)
                logger.info(f"Mensagens enviadas carregadas: {len(mensagens)} registros.")
                return mensagens
        except FileNotFoundError:
            logger.warning(f"Arquivo {MENSAGENS_ENVIADAS_FILE} não encontrado. Criando novo registro.")
            return {}

    def salvar_mensagens_enviadas(self):
        try:
            with open(MENSAGENS_ENVIADAS_FILE, 'w') as f:
                json.dump(self.mensagens_enviadas, f)
            logger.info(f"Mensagens enviadas salvas com sucesso.")
        except Exception as e:
            logger.error(f"Erro ao salvar mensagens enviadas: {str(e)}")

    def limpar_mensagens_antigas(self):
        logger.info("Limpando mensagens antigas (mais de 30 dias)...")
        agora = datetime.now()
        mensagens_removidas = 0
        for cliente_id, data_envio_str in list(self.mensagens_enviadas.items()):
            data_envio = datetime.fromisoformat(data_envio_str)
            if (agora - data_envio).days >= 30:
                del self.mensagens_enviadas[cliente_id]
                mensagens_removidas += 1
        self.salvar_mensagens_enviadas()
        logger.info(f"Limpeza concluída. {mensagens_removidas} mensagens antigas removidas.")

def criar_cupom_shopify(nome, telefone, total_gasto):
    desconto = 20 if total_gasto >= 5000 else 15 if total_gasto >= 2000 else 10 if total_gasto >= 1000 else 5 if total_gasto >= 500 else 0
    categoria = "5000" if total_gasto >= 5000 else "2000" if total_gasto >= 2000 else "1000" if total_gasto >= 1000 else "500" if total_gasto >= 500 else "0"

    if desconto == 0:
        return None

    nome_limpo = re.sub(r'[^a-zA-Z]', '', nome)
    prefixo_nome = nome_limpo[:5].upper().ljust(5, 'X')
    sufixo_telefone = telefone[-5:] if len(telefone) >= 5 else telefone.zfill(5)[-5:]
    codigo_cupom = f"{prefixo_nome}{sufixo_telefone}{categoria}"

    data_inicio = datetime.now()
    data_fim = data_inicio + timedelta(days=7)

    price_rule_data = {
        "price_rule": {
            "title": f"Desconto de {desconto}% para {nome}",
            "target_type": "line_item",
            "target_selection": "all",
            "allocation_method": "across",
            "value_type": "percentage",
            "value": f"-{desconto}.0",
            "customer_selection": "all",
            "starts_at": data_inicio.isoformat(),
            "ends_at": data_fim.isoformat()
        }
    }

    try:
        session = requests_retry_session()
        response = session.post(
            f"https://{SHOP_NAME}/admin/api/2023-01/price_rules.json",
            json=price_rule_data,
            headers={"X-Shopify-Access-Token": ACCESS_TOKEN}
        )
        response.raise_for_status()
        price_rule = response.json()['price_rule']
        
        discount_code_data = {
            "discount_code": {
                "code": codigo_cupom,
                "price_rule_id": price_rule['id']
            }
        }
        response = session.post(
            f"https://{SHOP_NAME}/admin/api/2023-01/price_rules/{price_rule['id']}/discount_codes.json",
            json=discount_code_data,
            headers={"X-Shopify-Access-Token": ACCESS_TOKEN}
        )
        response.raise_for_status()
        
        logger.info(f"Cupom criado com sucesso: {codigo_cupom} ({desconto}% de desconto, válido até {data_fim.strftime('%d/%m/%Y')}).")
        return {
            "codigo": codigo_cupom,
            "desconto": desconto,
            "validade": data_fim.strftime("%d/%m/%Y")
        }
    except requests.RequestException as e:
        logger.error(f"Erro ao criar cupom na Shopify: {str(e)}")
        return None

def buscar_todos_pedidos_cliente(customer_id):
    logger.info(f"Buscando todos os pedidos do cliente {customer_id}...")
    pedidos = []
    url = f"https://{SHOP_NAME}/admin/api/2023-01/orders.json?customer_id={customer_id}&status=any&limit=250"
    
    try:
        session = requests_retry_session()
        while url:
            response = session.get(url, headers={"X-Shopify-Access-Token": ACCESS_TOKEN})
            response.raise_for_status()
            
            data = response.json()
            if 'orders' in data:
                pedidos.extend(data['orders'])
                logger.info(f"Encontrados {len(data['orders'])} pedidos nesta página.")
            else:
                logger.warning(f"Não foram encontrados pedidos para o cliente {customer_id} nesta página.")
            
            url = response.links.get('next', {}).get('url')
        logger.info(f"Total de {len(pedidos)} pedidos encontrados para o cliente {customer_id}.")
        return pedidos
    except requests.RequestException as e:
        logger.error(f"Erro ao buscar pedidos: {str(e)}")
        return []

def calcular_total_gasto_cliente(customer_id):
    logger.info(f"Calculando total gasto pelo cliente {customer_id}...")
    pedidos = buscar_todos_pedidos_cliente(customer_id)
    total_gasto = sum(float(pedido['total_price']) for pedido in pedidos)
    logger.info(f"Total gasto pelo cliente {customer_id}: R${total_gasto:.2f}")
    return total_gasto

def buscar_pedidos_dia_anterior():
    hoje = datetime.now(pytz.UTC).date()
    ontem = hoje - timedelta(days=1)
    data_busca = ontem.strftime('%Y-%m-%d')
    logger.info(f"Buscando pedidos do dia anterior ({data_busca})...")

    pedidos = []
    url = f"https://{SHOP_NAME}/admin/api/2023-01/orders.json?created_at_min={data_busca}T00:00:00Z&created_at_max={data_busca}T23:59:59Z&status=any&limit=250"
    
    try:
        session = requests_retry_session()
        while url:
            response = session.get(url, headers={"X-Shopify-Access-Token": ACCESS_TOKEN})
            response.raise_for_status()
            
            data = response.json()
            if 'orders' in data:
                pedidos.extend(data['orders'])
                logger.info(f"Encontrados {len(data['orders'])} pedidos nesta página.")
            else:
                logger.warning(f"Não foram encontrados pedidos para a data {data_busca} nesta página.")
            
            url = response.links.get('next', {}).get('url')
        logger.info(f"Total de {len(pedidos)} pedidos encontrados para a data {data_busca}.")
        return pedidos
    except requests.RequestException as e:
        logger.error(f"Erro ao buscar pedidos: {str(e)}")
        return []

def extrair_dados_clientes(pedidos):
    logger.info("Extraindo dados dos clientes a partir dos pedidos...")
    clientes = {}
    for pedido in pedidos:
        if not isinstance(pedido, dict):
            logger.warning(f"Pedido inválido encontrado: {pedido}")
            continue
        
        customer_id = pedido.get('customer', {}).get('id')
        if not customer_id:
            logger.warning(f"ID do cliente não encontrado no pedido: {pedido.get('id')}")
            continue

        if customer_id not in clientes:
            shipping_address = pedido.get('shipping_address') or {}
            nome = shipping_address.get('name', 'Nome não disponível')
            telefone = formatar_telefone(shipping_address.get('phone', ''))
            total_gasto = calcular_total_gasto_cliente(customer_id)
            clientes[customer_id] = {
                'nome': nome,
                'email': pedido.get('email', 'Email não disponível'),
                'telefone': telefone,
                'total_gasto': total_gasto
            }
            logger.info(f"Dados do cliente {nome} extraídos.")

    logger.info(f"Dados de {len(clientes)} clientes extraídos.")
    return list(clientes.values())

def formatar_telefone(telefone):
    if not telefone:
        return ''
    numeros = re.sub(r'\D', '', telefone)
    if not numeros.startswith('55'):
        numeros = '55' + numeros
    if len(numeros) < 12:
        return ''
    return numeros[:13]

def send_whatsapp_message(number, message):
    logger.info(f"Enviando mensagem de WhatsApp para {number}...")
    url = f"{EVOLUTION_ENDPOINT}/message/sendText/{EVOLUTION_INSTANCE}"
    
    payload = {
        "number": number,
        "textMessage": {"text": message},
        "options": {
            "delay": 1000,
            "presence": "composing",
            "linkPreview": True
        }
    }
    headers = {
        "apikey": EVOLUTION_API_KEY,
        "Content-Type": "application/json"
    }

    try:
        session = requests_retry_session()
        response = session.post(url, headers=headers, json=payload)
        response.raise_for_status()
        logger.info(f"Mensagem de WhatsApp enviada com sucesso para {number}.")
        return True
    except requests.RequestException as e:
        logger.error(f"Falha ao enviar mensagem de WhatsApp para {number}. Erro: {str(e)}")
        return False

def processar_clientes_dia_anterior(sistema_recompensas):
    logger.info("Processando clientes do dia anterior...")
    pedidos = buscar_pedidos_dia_anterior()
    clientes = extrair_dados_clientes(pedidos)
    
    for cliente in clientes:
        oferta = sistema_recompensas.gerar_oferta(cliente['email'], cliente['nome'], cliente['telefone'], cliente['total_gasto'])
        
        if oferta:
            logger.info(f"Processando cliente: {cliente['nome']}")
            logger.info(f"Total gasto: R${cliente['total_gasto']:.2f}")
            logger.info(f"Oferta gerada: {oferta}")
            
            if send_whatsapp_message(cliente['telefone'], oferta):
                logger.info("Mensagem de WhatsApp enviada com sucesso.")
            else:
                logger.warning("Falha ao enviar mensagem de WhatsApp.")
            
            logger.info("--------------------")
            
            intervalo = random.randint(120, 300)
            logger.info(f"Aguardando {intervalo} segundos antes da próxima mensagem...")
            time.sleep(intervalo)
        else:
            logger.info(f"Nenhuma oferta gerada para {cliente['nome']} neste momento.")
            
            
def executar():
    logger.info("Iniciando o processo de busca de pedidos do dia anterior, geração de ofertas e envio de mensagens...")
    sistema_recompensas = SistemaRecompensas()
    processar_clientes_dia_anterior(sistema_recompensas)
    sistema_recompensas.limpar_mensagens_antigas()
    logger.info("Processo concluído.")

def executar_diariamente():
    schedule.every().day.at("09:00").do(executar)
    logger.info("Próxima execução agendada para amanhã às 09:00.")

if __name__ == "__main__":
    logger.info("Script iniciado.")

    # Verificar conexão com Shopify
    sistema_recompensas = SistemaRecompensas()
    if sistema_recompensas.verificar_conexao_shopify():
        logger.info("Conexão com Shopify estabelecida com sucesso.")
    else:
        logger.error("Falha ao conectar com Shopify. Verifique suas credenciais.")
        sys.exit(1)  # Encerrar o script em caso de falha na conexão

    # Aguarda até as 09:00 da primeira execução
    schedule.every().day.at("09:00").do(executar)

    while True:
        schedule.run_pending()
        now = datetime.now()
        proxima_execucao = schedule.next_run()
        tempo_restante = (proxima_execucao - now).total_seconds()
        logger.info(f"Próxima execução em {tempo_restante:.0f} segundos...")
        time.sleep(60)
