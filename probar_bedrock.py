"""
Paso 1 - Prueba de conexion con Claude Haiku 5.5 en Amazon Bedrock.

Uso:
  1) pip install boto3
  2) Define tus claves como variables de entorno (NO las escribas en este archivo):
       Windows (PowerShell):
         $env:AWS_ACCESS_KEY_ID="..."
         $env:AWS_SECRET_ACCESS_KEY="..."
         $env:AWS_REGION="us-east-1"
       Mac / Linux:
         export AWS_ACCESS_KEY_ID="..."
         export AWS_SECRET_ACCESS_KEY="..."
         export AWS_REGION="us-east-1"
  3) python probar_bedrock.py
"""
import os
import sys

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

REGION = os.environ.get("AWS_REGION", "us-east-1")
MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "us.anthropic.claude-haiku-5-5")

print(f"Region: {REGION}")
print(f"Modelo: {MODEL_ID}")

try:
    client = boto3.client("bedrock-runtime", region_name=REGION)
    resp = client.converse(
        modelId=MODEL_ID,
        messages=[{
            "role": "user",
            "content": [{"text": "Responde en una sola linea: que cuenta del PCGE peruano se usa para el IGV?"}],
        }],
        inferenceConfig={"maxTokens": 200},
    )
    texto = resp["output"]["message"]["content"][-1]["text"]
    uso = resp["usage"]
    print("\nCONEXION OK")
    print("Respuesta de Claude:", texto.strip())
    print(f"Tokens usados: entrada {uso['inputTokens']}, salida {uso['outputTokens']}")
except NoCredentialsError:
    sys.exit("\nERROR: no se encontraron las claves. Revisa AWS_ACCESS_KEY_ID y AWS_SECRET_ACCESS_KEY.")
except ClientError as e:
    codigo = e.response["Error"]["Code"]
    mensaje = e.response["Error"]["Message"]
    print(f"\nERROR {codigo}: {mensaje}")
    if codigo == "AccessDeniedException":
        print("-> Al usuario IAM le faltan permisos de Bedrock o el modelo no esta habilitado en tu cuenta.")
    elif codigo == "ValidationException":
        print("-> Revisa el ID del modelo y la region (prueba con 'global.anthropic.claude-haiku-5-5').")
    elif codigo == "UnrecognizedClientException":
        print("-> Las claves son incorrectas o estan desactivadas.")
    sys.exit(1)
