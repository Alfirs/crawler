import express from 'express';
import cors from 'cors';
import compression from 'compression';
import 'express-async-errors';

import { logger } from '@/config/logger.config';
import { config } from '@/config/env.config';
import { database } from '@/config/database.config';
import { messagesRouter } from './controllers/messages.controller';
import { IntegrationEventSubscriberService } from './services/integration-event-subscriber.service';
import { EventPublisherService } from '@integrations/services/event-publisher.service';
import { authMiddleware } from '@/modules/auth/src/middleware/auth.middleware';

const app = express();
const subscriber = new IntegrationEventSubscriberService(new EventPublisherService());

// Middleware
app.use(compression());
app.use(cors());
app.use(express.json({ limit: '10mb' }));
app.use(express.urlencoded({ extended: true, limit: '10mb' }));

// Health check
app.get('/health', (req, res) => {
  res.json({
    status: 'OK',
    service: 'messages',
    timestamp: new Date().toISOString(),
    database: database.isConnected ? 'connected' : 'disconnected',
    broker: subscriber.getStatus(),
  });
});

// API routes
app.use('/messages', authMiddleware, messagesRouter);

// Error handling
app.use((err: any, req: express.Request, res: express.Response, next: express.NextFunction) => {
  logger.error(err);
  res.status(err.status || 500).json({
    error: {
      code: err.code || 'INTERNAL_ERROR',
      message: err.message || 'Internal server error',
    },
  });
});

// 404 handler
app.use('*', (req, res) => {
  res.status(404).json({
    error: {
      code: 'NOT_FOUND',
      message: 'Endpoint not found',
    },
  });
});

// Start server (skip when running under tests)
if (process.env.NODE_ENV !== 'test') {
  (async () => {
    try {
      await database.connect();
      await subscriber.start();

      const port = process.env.PORT || 3002;
      app.listen(port, () => {
        logger.info(`Messages Service started on port ${port}`);
      });
    } catch (error) {
      logger.error({ err: error }, 'Failed to start messages service');
      process.exit(1);
    }
  })();
}

export { app };
