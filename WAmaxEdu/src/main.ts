import express from 'express';
import cors from 'cors';
import compression from 'compression';
import 'express-async-errors';
import path from 'path';

import { config } from './config/env.config';
import { logger } from './config/logger.config';
import { database } from './config/database.config';
import { redis } from './config/redis.config';

// Import module routers
import { integrationsRouter } from './modules/integrations/src/controllers/integrations.controller';
import { messagesRouter } from './modules/messages/src/controllers/messages.controller';
import { IntegrationEventSubscriberService } from './modules/messages/src/services/integration-event-subscriber.service';
import { EventPublisherService } from './modules/integrations/src/services/event-publisher.service';
import { authRouter } from './modules/auth/src/controllers/auth.controller';
import { authMiddleware } from './modules/auth/src/middleware/auth.middleware';

const app = express();
const messagesSubscriber = new IntegrationEventSubscriberService(new EventPublisherService());

// Middleware
app.use(compression());
app.use(cors());
app.use(express.json({ limit: '10mb' }));
app.use(express.urlencoded({ extended: true, limit: '10mb' }));

// Health check
app.get('/health', (req, res) => {
  res.json({ status: 'OK', timestamp: new Date().toISOString() });
});

// Static playground UI
const playgroundPath = path.join(process.cwd(), 'public', 'playground');
app.use('/ui', express.static(playgroundPath));

// API routes
app.use('/integrations', integrationsRouter); // legacy path
app.use('/api/v1/integrations', integrationsRouter); // preferred path
app.use('/api/v1/auth', authRouter);
app.use('/api/v1/messages', authMiddleware, messagesRouter);

// Error handling
app.use((err: any, req: express.Request, res: express.Response, next: express.NextFunction) => {
  logger.error(err);
  res.status(err.status || 500).json({
    error: {
      code: err.code || 'INTERNAL_ERROR',
      message: err.message || 'Internal server error'
    }
  });
});

// 404 handler
app.use('*', (req, res) => {
  res.status(404).json({
    error: {
      code: 'NOT_FOUND',
      message: 'Endpoint not found'
    }
  });
});

// Start server
async function startServer() {
  try {
    // Initialize connections
    await database.connect();
    await redis.connect();
    await messagesSubscriber.start();

    const port = config.PORT || 3000;
    app.listen(port, () => {
      logger.info(`WAmaxEdu Platform started on port ${port}`);
    });
  } catch (error) {
    logger.error({ err: error }, 'Failed to start server');
    process.exit(1);
  }
}

startServer();
