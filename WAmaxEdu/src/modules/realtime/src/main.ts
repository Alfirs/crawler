import http from 'http';
import express from 'express';
import cors from 'cors';
import compression from 'compression';
import 'express-async-errors';
import { Server } from 'socket.io';

import { logger } from '@/config/logger.config';
import { config } from '@/config/env.config';
import { verifySocketAuth } from '@/modules/auth/src/middleware/auth.middleware';
import { MessageEventSubscriberService } from './services/message-event-subscriber.service';
import { MessageCreated } from '@/modules/messages/src/events/message-created.event';
import { MessageStatusUpdated } from '@/modules/messages/src/events/status-updated.event';

const app = express();
const server = http.createServer(app);
const io = new Server(server, {
  cors: {
    origin: '*',
    methods: ['GET', 'POST'],
  },
});

const subscriber = new MessageEventSubscriberService();

// Middleware
app.use(compression());
app.use(cors());
app.use(express.json({ limit: '10mb' }));
app.use(express.urlencoded({ extended: true, limit: '10mb' }));

// Health check
app.get('/health', (req, res) => {
  res.json({
    status: 'OK',
    service: 'realtime',
    timestamp: new Date().toISOString(),
    broker: subscriber.getStatus(),
  });
});

io.use((socket, next) => {
  if (!config.AUTH_REQUIRED) {
    next();
    return;
  }

  const apiKey = socket.handshake.auth?.apiKey || socket.handshake.headers['x-api-key'];
  const token = socket.handshake.auth?.token;
  const authorization = socket.handshake.headers['authorization'] as string | undefined;

  const result = verifySocketAuth({
    apiKey: typeof apiKey === 'string' ? apiKey : undefined,
    token: typeof token === 'string' ? token : undefined,
    authorization,
  });

  if (!result.ok) {
    next(new Error('UNAUTHORIZED'));
    return;
  }

  socket.data.subject = result.subject;
  next();
});

io.on('connection', (socket) => {
  const accountId = socket.handshake.auth?.accountId || socket.handshake.query.accountId;
  if (typeof accountId === 'string' && accountId.length > 0) {
    socket.join(`account:${accountId}`);
  }

  socket.on('disconnect', () => {
    logger.info({ socketId: socket.id }, 'Realtime client disconnected');
  });
});

function emitToAccount(eventName: string, accountId: string | undefined, payload: any): void {
  if (accountId) {
    io.to(`account:${accountId}`).emit(eventName, payload);
    return;
  }
  io.emit(eventName, payload);
}

async function startSubscriber(): Promise<void> {
  await subscriber.start({
    onMessageCreated: (event: MessageCreated) => emitToAccount('messages.created', event.accountId, event),
    onStatusUpdated: (event: MessageStatusUpdated) => emitToAccount('messages.status.updated', event.accountId, event),
  });
}

if (process.env.NODE_ENV !== 'test') {
  (async () => {
    try {
      await startSubscriber();
      const port = process.env.PORT || 3003;
      server.listen(port, () => {
        logger.info(`Realtime Gateway started on port ${port}`);
      });
    } catch (error) {
      logger.error({ err: error }, 'Failed to start Realtime Gateway');
      process.exit(1);
    }
  })();
}

export { app, io };
