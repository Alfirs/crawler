import amqp, { Channel, Connection, ConsumeMessage } from 'amqplib';
import { MessageEventPublisher } from '@/modules/messages/src/services/message-event-publisher.service';
import { MessageCreated } from '@/modules/messages/src/events/message-created.event';
import { MessageStatusUpdated } from '@/modules/messages/src/events/status-updated.event';
import { config } from '@/config/env.config';
import { logger } from '@/config/logger.config';

const EXCHANGE_NAME = 'messages.events';
const RETRY_EXCHANGE_NAME = 'messages.events.retry';
const DLQ_EXCHANGE_NAME = 'messages.events.dlq';

interface RealtimeHandlers {
  onMessageCreated: (event: MessageCreated) => Promise<void> | void;
  onStatusUpdated: (event: MessageStatusUpdated) => Promise<void> | void;
}

export class MessageEventSubscriberService {
  private connection: Connection | null = null;
  private channel: Channel | null = null;
  private readonly queueName = config.REALTIME_BROKER_QUEUE;
  private readonly retryQueueName = `${this.queueName}.retry`;
  private readonly dlqQueueName = `${this.queueName}.dlq`;

  constructor(private readonly messagePublisher: MessageEventPublisher = new MessageEventPublisher()) {}

  async start(handlers: RealtimeHandlers): Promise<void> {
    if (config.RABBITMQ_ENABLED) {
      await this.startRabbitConsumer(handlers);
      logger.info('MessageEventSubscriberService started (RabbitMQ)');
      return;
    }

    if (config.NODE_ENV === 'production') {
      throw new Error('BROKER_DISABLED_IN_PROD');
    }

    this.startInMemory(handlers);
    logger.info('MessageEventSubscriberService started (in-memory)');
  }

  async stop(): Promise<void> {
    if (this.channel) {
      await this.channel.close();
      this.channel = null;
    }
    if (this.connection) {
      await this.connection.close();
      this.connection = null;
    }
  }

  getStatus(): 'connected' | 'disabled' | 'error' {
    if (!config.RABBITMQ_ENABLED) {
      return 'disabled';
    }
    return this.channel ? 'connected' : 'error';
  }

  private startInMemory(handlers: RealtimeHandlers): void {
    this.messagePublisher.subscribe('messages.created', (event) => handlers.onMessageCreated(event as MessageCreated));
    this.messagePublisher.subscribe('messages.status.updated', (event) =>
      handlers.onStatusUpdated(event as MessageStatusUpdated)
    );
  }

  private async startRabbitConsumer(handlers: RealtimeHandlers): Promise<void> {
    if (!config.RABBITMQ_URI) {
      throw new Error('RABBITMQ_URI_MISSING');
    }

    this.connection = await amqp.connect(config.RABBITMQ_URI);
    this.connection.on('error', (err) => logger.error({ err }, 'RabbitMQ connection error'));
    this.connection.on('close', () => {
      logger.warn('RabbitMQ connection closed');
      this.channel = null;
    });

    this.channel = await this.connection.createChannel();
    await this.channel.assertExchange(EXCHANGE_NAME, 'topic', { durable: true });
    await this.channel.assertExchange(RETRY_EXCHANGE_NAME, 'topic', { durable: true });
    await this.channel.assertExchange(DLQ_EXCHANGE_NAME, 'topic', { durable: true });

    await this.channel.assertQueue(this.queueName, { durable: true });
    await this.channel.bindQueue(this.queueName, EXCHANGE_NAME, 'messages.created');
    await this.channel.bindQueue(this.queueName, EXCHANGE_NAME, 'messages.status.updated');

    await this.channel.assertQueue(this.retryQueueName, {
      durable: true,
      arguments: {
        'x-message-ttl': config.BROKER_RETRY_DELAY_MS,
        'x-dead-letter-exchange': EXCHANGE_NAME,
      },
    });
    await this.channel.bindQueue(this.retryQueueName, RETRY_EXCHANGE_NAME, 'messages.created');
    await this.channel.bindQueue(this.retryQueueName, RETRY_EXCHANGE_NAME, 'messages.status.updated');

    await this.channel.assertQueue(this.dlqQueueName, { durable: true });
    await this.channel.bindQueue(this.dlqQueueName, DLQ_EXCHANGE_NAME, '#');

    await this.channel.prefetch(config.BROKER_PREFETCH);
    await this.channel.consume(this.queueName, (msg) => this.handleMessage(msg, handlers), { noAck: false });
  }

  private async handleMessage(msg: ConsumeMessage | null, handlers: RealtimeHandlers): Promise<void> {
    if (!msg || !this.channel) {
      return;
    }

    const routingKey = msg.fields.routingKey;
    let payload: any;

    try {
      payload = JSON.parse(msg.content.toString('utf-8'));
    } catch (error) {
      await this.sendToDlq(msg, routingKey, msg.content.toString('utf-8'), error);
      return;
    }

    try {
      if (routingKey === 'messages.created') {
        await handlers.onMessageCreated(payload as MessageCreated);
      } else if (routingKey === 'messages.status.updated') {
        await handlers.onStatusUpdated(payload as MessageStatusUpdated);
      } else {
        logger.warn({ routingKey }, 'Unhandled routing key, message ignored');
      }

      this.channel.ack(msg);
    } catch (error) {
      await this.retryOrDlq(msg, routingKey, payload, error);
    }
  }

  private async retryOrDlq(
    msg: ConsumeMessage,
    routingKey: string,
    payload: any,
    error: unknown
  ): Promise<void> {
    if (!this.channel) {
      return;
    }

    const headers = msg.properties.headers || {};
    const retryCount = Number(headers['x-retry-count'] || 0);

    try {
      if (retryCount < config.BROKER_MAX_RETRIES) {
        this.channel.publish(
          RETRY_EXCHANGE_NAME,
          routingKey,
          Buffer.from(JSON.stringify(payload)),
          {
            contentType: 'application/json',
            persistent: true,
            headers: {
              'x-retry-count': retryCount + 1,
            },
          }
        );
        this.channel.ack(msg);
        logger.warn({ routingKey, retryCount }, 'Realtime event requeued for retry');
        return;
      }

      this.channel.publish(
        DLQ_EXCHANGE_NAME,
        routingKey,
        Buffer.from(JSON.stringify(payload)),
        {
          contentType: 'application/json',
          persistent: true,
          headers: {
            'x-retry-count': retryCount,
            'x-error': error instanceof Error ? error.message : 'UNKNOWN_ERROR',
          },
        }
      );
      this.channel.ack(msg);
      logger.error({ routingKey, retryCount, err: error }, 'Realtime event sent to DLQ');
    } catch (publishError) {
      logger.error({ err: publishError }, 'Failed to publish realtime retry/DLQ event');
      this.channel.nack(msg, false, true);
    }
  }

  private async sendToDlq(
    msg: ConsumeMessage,
    routingKey: string,
    rawPayload: string,
    error: unknown
  ): Promise<void> {
    if (!this.channel) {
      return;
    }

    try {
      this.channel.publish(
        DLQ_EXCHANGE_NAME,
        routingKey,
        Buffer.from(rawPayload),
        {
          contentType: 'application/json',
          persistent: true,
          headers: {
            'x-error': error instanceof Error ? error.message : 'INVALID_JSON',
          },
        }
      );
      this.channel.ack(msg);
      logger.error({ routingKey, err: error }, 'Invalid realtime payload sent to DLQ');
    } catch (publishError) {
      logger.error({ err: publishError }, 'Failed to publish realtime DLQ event');
      this.channel.nack(msg, false, true);
    }
  }
}
