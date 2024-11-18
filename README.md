# Rewards System

This project is a Python-based rewards system that integrates with Shopify and sends WhatsApp messages to customers based on their spending. It calculates discounts for customers based on their total spending and generates discount coupons that are sent via WhatsApp.

## Features

- Connects to Shopify API to retrieve customer orders.
- Calculates discounts based on customer spending.
- Generates discount coupons and sends them to customers via WhatsApp.
- Logs all activities for monitoring and debugging.
- Cleans up old messages sent to customers.

## Requirements

- Python 3.x
- `requests` library
- `pytz` library
- `schedule` library
- `python-dotenv` library
- Access to Shopify API
- Access to WhatsApp messaging API

## Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd <repository-directory>
   ```

2. Install the required packages:
   ```bash
   pip install requests pytz schedule python-dotenv
   ```

3. Create a `.env` file in the project root and add the following environment variables:
   ```plaintext
   SHOP_NAME=<your-shop-name>
   ACCESS_TOKEN=<your-access-token>
   EVOLUTION_ENDPOINT=<your-evolution-endpoint>
   EVOLUTION_INSTANCE=<your-evolution-instance>
   EVOLUTION_API_KEY=<your-evolution-api-key>
   SHOP_URL=<your-shop-url>
   ```

## Usage

Run the script to start the rewards system:
```bash
python rewards_system.py
```

The script will check the connection to Shopify, process customer orders from the previous day, generate offers, and send WhatsApp messages. It is scheduled to run daily at 08:00 AM (São Paulo timezone).

## Logging

All activities are logged into a file named `recompensas.log`. You can check this file for any errors or information regarding the execution of the script.

## Functions

- `verificar_conexao_shopify()`: Checks the connection to the Shopify API.
- `calcular_desconto(total_gasto)`: Calculates the discount based on total spending.
- `gerar_oferta(cliente_id, nome, telefone, total_gasto)`: Generates an offer for the customer.
- `carregar_mensagens_enviadas()`: Loads sent messages from a JSON file.
- `salvar_mensagens_enviadas()`: Saves sent messages to a JSON file.
- `limpar_mensagens_antigas()`: Cleans up messages older than 30 days.
- `criar_cupom_shopify(nome, telefone, total_gasto)`: Creates a discount coupon in Shopify.
- `buscar_todos_pedidos_cliente(customer_id)`: Retrieves all orders for a specific customer.
- `calcular_total_gasto_cliente(customer_id)`: Calculates the total spending of a customer.
- `buscar_pedidos_dia_anterior()`: Retrieves orders from the previous day.
- `extrair_dados_clientes(pedidos)`: Extracts customer data from orders.
- `formatar_telefone(telefone)`: Formats the phone number.
- `send_whatsapp_message(number, message)`: Sends a WhatsApp message to a specified number.
- `processar_clientes_dia_anterior(sistema_recompensas)`: Processes customers from the previous day.
- `executar()`: Executes the main process of the rewards system.
- `executar_diariamente()`: Schedules the daily execution of the script.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
