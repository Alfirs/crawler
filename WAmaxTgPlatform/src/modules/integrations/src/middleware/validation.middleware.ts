import { Request, Response, NextFunction } from 'express';
import { Validator, Schema } from 'jsonschema';
import { logger } from '@/config/logger.config';

const validator = new Validator();

export function validateSchema(schema: Schema | any) {
  return (req: Request, res: Response, next: NextFunction): void => {
    try {
      const result = validator.validate(req.body, schema);

      if (!result.valid) {
        const errors = result.errors.map(err => ({
          field: err.property,
          message: err.message
        }));

        logger.warn({ errors, body: req.body }, 'Validation failed');

        res.status(400).json({
          error: {
            code: 'VALIDATION_ERROR',
            message: 'Request validation failed',
            details: errors
          }
        });
        return;
      }

      next();
    } catch (error) {
      logger.error({ err: error }, 'Validation middleware error');
      res.status(500).json({
        error: {
          code: 'VALIDATION_SYSTEM_ERROR',
          message: 'Validation system error'
        }
      });
    }
  };
}
