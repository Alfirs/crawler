import amqp, { Channel, Connection } from 'amqplib';
import { EventEmitter2 } from 'eventemitter2';
import { MessageCreated } from '../events/message-created.event';
import { MessageStatusUpdated } from '../events/status-updated.event';
import { config } from '@/config/env.config';
import { logger } from '@/config/logger.config';

const eventEmitter = new EventEmitter2();
const EXCHANGE_NAME = 'messages.events';

class BrokerAdapter {
  private connection: Connection | null = null;
  private channel: Channel | null = null;

  private async getChannel(): Promise<Channel | null> {
    if (!config.RABBITMQ_ENABLED) {
      return null;
    }

    if (!config.RABBITMQ_URI) {
      logger.error('RabbitMQ enabled but RABBITMQ_URI is not set');
      throw new Error('RABBITMQ_URI_MISSING');
    }

    if (this.channel) {
      return this.channel;
    }

    try {
      this.connection = await amqp.connect(config.RABBITMQ_URI);
      this.connection.on('error', (err) => logger.error({ err }, 'RabbitMQ connection error'));
      this.connection.on('close', () => {
        logger.warn('RabbitMQ connection closed, resetting channel');
        this.channel = null;
      });

      this.channel = await this.connection.createChannel();
      await this.channel.assertExchange(EXCHANGE_NAME, 'topic', { durable: true });

      return this.channel;
    } catch (error) {
      logger.error({ err: error }, 'Failed to establish RabbitMQ channel');
      this.channel = null;
      throw new Error('RABBITMQ_CONNECTION_FAILED');
    }
  }

  async publish(eventName: string, payload: any): Promise<void> {
    const channel = await this.getChannel();

    if (channel) {
      channel.publish(
        EXCHANGE_NAME,
        eventName,
        Buffer.from(JSON.stringify(payload)),
        {
          contentType: 'application/json',
          persistent: true,
        }
      );
      return;
    }

    if (config.NODE_ENV === 'production' || config.RABBITMQ_ENABLED) {
      throw new Error('BROKER_DISABLED_IN_PROD');
    }

    eventEmitter.emit(eventName, payload);
  }

  subscribe(eventName: string, handler: (event: any) => void): void {
    eventEmitter.on(eventName, handler);
  }

  async health(): Promise<'connected' | 'disabled' | 'error'> {
    if (!config.RABBITMQ_ENABLED) {
      return 'disabled';
    }
    try {
      const channel = await this.getChannel();
      return channel ? 'connected' : 'error';
    } catch (error) {
      logger.error({ err: error }, 'BrokerAdapter health check failed');
      return 'error';
    }
  }
}

const brokerAdapter = new BrokerAdapter();

export class MessageEventPublisher {
  async ensureConnected(): Promise<void> {
    if (!config.RABBITMQ_ENABLED) {
      if (config.NODE_ENV === 'production') {
        throw new Error('BROKER_DISABLED_IN_PROD');
      }
      return;
    }
    await brokerAdapter['getChannel']();
  }

  async publishMessageCreated(event: MessageCreated): Promise<void> {
    try {
      await brokerAdapter.publish('messages.created', event);
      logger.info(`Published MessageCreated event: ${event.eventId}`);
    } catch (error) {
      logger.error({ err: error }, 'MessageEventPublisher.publishMessageCreated error');
      throw error;
    }
  }

  async publishStatusUpdated(event: MessageStatusUpdated): Promise<void> {
    try {
      await brokerAdapter.publish('messages.status.updated', event);
      logger.info(`Published MessageStatusUpdated event: ${event.eventId}`);
    } catch (error) {
      logger.error({ err: error }, 'MessageEventPublisher.publishStatusUpdated error');
      throw error;
    }
  }

  subscribe(eventName: string, handler: (event: any) => void): void {
    brokerAdapter.subscribe(eventName, handler);
  }
}
