import boto3
import json

lambda_client = boto3.client('lambda')

def lambda_handler(event, context):
    print('Received event:', event)
    return {
        'statusCode': 200,
        'body': json.dumps({'message': 'Hello from AWS Lambda!'})
    }
