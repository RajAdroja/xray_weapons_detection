import json
import asyncio
import aio_pika
import uuid
from datetime import datetime
from typing import Dict, List, Any, Callable
from rabbitmq_config import rabbitmq_settings
import logging

logger = logging.getLogger(__name__)

class RabbitMQService:
    def __init__(self):
        self.connection = None
        self.channel = None
        self.exchange = None
        
    async def connect(self):
        """Establish connection to RabbitMQ"""
        try:
            # Connect with larger frame size for big messages
            self.connection = await aio_pika.connect_robust(
                rabbitmq_settings.rabbitmq_url,
                client_properties={"connection_name": "xray_detector"},
                # Increase frame size to handle large messages (default is ~128KB)
                frame_max=2097152  # 2MB frame size
            )
            self.channel = await self.connection.channel()
            # Set channel prefetch to handle large messages better
            await self.channel.set_qos(prefetch_count=1)
            
            # Declare exchange
            self.exchange = await self.channel.declare_exchange(
                rabbitmq_settings.exchange_name,
                aio_pika.ExchangeType.DIRECT,
                durable=True
            )
            
            # Declare queues
            await self.channel.declare_queue(
                rabbitmq_settings.prediction_queue,
                durable=True
            )
            
            await self.channel.declare_queue(
                rabbitmq_settings.result_queue,
                durable=True
            )
            
            await self.channel.declare_queue(
                rabbitmq_settings.status_queue,
                durable=True
            )
            
            logger.info("Connected to RabbitMQ successfully")
            
        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")
            raise
    
    async def close(self):
        """Close RabbitMQ connection"""
        if self.connection:
            await self.connection.close()
            
    async def publish_prediction_task(self, task_data: Dict[str, Any]) -> str:
        """Publish a prediction task to the queue"""
        if not self.connection:
            await self.connect()
            
        # Use file_task_id as correlation_id if available, otherwise generate one
        correlation_id = task_data.get("file_task_id", str(uuid.uuid4()))
        
        message = aio_pika.Message(
            json.dumps(task_data).encode(),
            correlation_id=correlation_id,
            reply_to=rabbitmq_settings.result_queue
        )
        
        await self.exchange.publish(
            message,
            routing_key=rabbitmq_settings.routing_key
        )
        
        logger.info(f"Published prediction task with correlation_id: {correlation_id}")
        return correlation_id
    
    async def publish_status_update(self, task_id: str, status: str, error: str = None):
        """Publish task status update"""
        if not self.connection or self.connection.is_closed:
            await self.connect()
        
        status_data = {
            "task_id": task_id,
            "status": status,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if error:
            status_data["error"] = error
        
        message = aio_pika.Message(
            json.dumps(status_data).encode(),
            correlation_id=task_id
        )
        
        await self.channel.default_exchange.publish(
            message,
            routing_key=rabbitmq_settings.status_queue
        )
        
        logger.info(f"Published status update for task {task_id}: {status}")
    
    async def consume_prediction_tasks(self, callback: Callable):
        """Consume prediction tasks from the queue"""
        if not self.connection:
            await self.connect()
            
        queue = await self.channel.declare_queue(
            rabbitmq_settings.prediction_queue,
            durable=True
        )
        
        await queue.bind(self.exchange, rabbitmq_settings.routing_key)
        
        async def process_message(message: aio_pika.IncomingMessage):
            async with message.process():
                try:
                    task_data = json.loads(message.body.decode())
                    await callback(task_data, message.correlation_id, message.reply_to)
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
        
        await queue.consume(process_message)
    
    async def consume_results(self, callback: Callable):
        """Consume results from the result queue"""
        if not self.connection:
            await self.connect()
            
        queue = await self.channel.declare_queue(
            rabbitmq_settings.result_queue,
            durable=True
        )
        
        async def process_result_message(message: aio_pika.IncomingMessage):
            async with message.process():
                try:
                    message_size_kb = len(message.body) / 1024
                    logger.info(f"Processing result message {message.correlation_id} (size: {message_size_kb:.1f} KB)")
                    
                    result_data = json.loads(message.body.decode())
                    await callback(result_data, message.correlation_id)
                    
                    logger.info(f"Successfully processed result message {message.correlation_id}")
                except Exception as e:
                    logger.error(f"Error processing result message {message.correlation_id}: {e}")
                    # Don't re-raise to avoid message redelivery loop
        
        await queue.consume(process_result_message)
    
    async def consume_status_updates(self, callback: Callable):
        """Consume status updates from the queue"""
        if not self.connection or self.connection.is_closed:
            await self.connect()
            
        queue = await self.channel.get_queue(rabbitmq_settings.status_queue)
        
        async def process_status_message(message: aio_pika.IncomingMessage):
            async with message.process():
                try:
                    status_data = json.loads(message.body.decode())
                    await callback(status_data)
                except Exception as e:
                    logger.error(f"Error processing status message: {e}")
        
        await queue.consume(process_status_message)
        
    async def publish_result(self, result_data: Dict[str, Any], correlation_id: str, reply_to: str):
        """Publish prediction result"""
        if not self.connection:
            await self.connect()
        
        try:
            result_json = json.dumps(result_data)
            result_size_kb = len(result_json) / 1024
            
            message = aio_pika.Message(
                result_json.encode(),
                correlation_id=correlation_id,
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT  # Ensure message persistence
            )
            
            await self.channel.default_exchange.publish(
                message,
                routing_key=reply_to,
                mandatory=True  # Ensure message is routed to a queue
            )
            
            logger.info(f"Published result for correlation_id: {correlation_id} (size: {result_size_kb:.1f} KB)")
            
        except Exception as e:
            logger.error(f"Failed to publish result for correlation_id {correlation_id}: {e}")
            raise

# Global instance
rabbitmq_service = RabbitMQService()