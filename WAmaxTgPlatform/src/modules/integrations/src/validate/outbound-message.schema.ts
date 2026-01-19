import { JSONSchema7 } from 'json-schema';

export const outboundMessageSendSchema: JSONSchema7 = {
  $id: 'OutboundMessageSendRequest',
  type: 'object',
  properties: {
    channel: {
      type: 'string',
      enum: ['WHATSAPP'],
      description: 'Channel for message delivery'
    },
    accountId: {
      type: 'string',
      minLength: 1,
      description: 'Account identifier'
    },
    conversationRef: {
      type: 'object',
      properties: {
        type: {
          type: 'string',
          enum: ['EXTERNAL_PARTICIPANT', 'THREAD']
        },
        id: {
          type: 'string',
          minLength: 1
        }
      },
      required: ['type', 'id']
    },
    context: {
      type: 'object',
      properties: {
        replyToMessageId: {
          type: 'string'
        },
        forwarded: {
          type: 'boolean'
        },
        metadata: {
          type: 'object'
        }
      }
    },
    requestedAt: {
      type: 'string',
      format: 'date-time'
    },
    message: {
      type: 'object',
      properties: {
        clientMessageId: {
          type: 'string',
          minLength: 1
        },
        kind: {
          type: 'string',
          enum: ['TEXT', 'MEDIA', 'LOCATION', 'CONTACT', 'INTERACTIVE', 'REACTION']
        },
        content: {
          oneOf: [
            { $ref: '#/$defs/TextContent' },
            { $ref: '#/$defs/MediaContent' },
            { $ref: '#/$defs/LocationContent' },
            { $ref: '#/$defs/ContactContent' },
            { $ref: '#/$defs/InteractiveContent' },
            { $ref: '#/$defs/ReactionContent' }
          ]
        }
      },
      required: ['clientMessageId', 'kind', 'content']
    }
  },
  required: ['channel', 'accountId', 'conversationRef', 'message'],
  $defs: {
    TextContent: {
      type: 'object',
      properties: {
        text: {
          type: 'string',
          minLength: 1
        },
        format: {
          type: 'string',
          enum: ['PLAIN', 'MARKDOWN', 'HTML']
        }
      },
      required: ['text', 'format']
    },
    MediaContent: {
      type: 'object',
      properties: {
        mediaType: {
          type: 'string',
          enum: ['IMAGE', 'VIDEO', 'AUDIO', 'FILE']
        },
        source: {
          oneOf: [
            {
              type: 'object',
              properties: {
                url: { type: 'string', format: 'uri' }
              },
              required: ['url']
            },
            {
              type: 'object',
              properties: {
                fileId: { type: 'string', minLength: 1 }
              },
              required: ['fileId']
            }
          ]
        },
        caption: { type: 'string' },
        filename: { type: 'string' },
        mimeType: { type: 'string' },
        sizeBytes: { type: 'number', minimum: 0 },
        thumbnail: {
          type: 'object',
          properties: {
            url: { type: 'string', format: 'uri' },
            fileId: { type: 'string', minLength: 1 }
          }
        }
      },
      required: ['mediaType', 'source']
    },
    LocationContent: {
      type: 'object',
      properties: {
        latitude: { type: 'number' },
        longitude: { type: 'number' },
        address: { type: 'string' },
        title: { type: 'string' }
      },
      required: ['latitude', 'longitude']
    },
    ContactContent: {
      type: 'object',
      properties: {
        contacts: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              displayName: { type: 'string', minLength: 1 },
              phones: {
                type: 'array',
                items: {
                  type: 'object',
                  properties: {
                    number: { type: 'string', minLength: 1 },
                    label: { type: 'string' }
                  },
                  required: ['number']
                }
              },
              emails: {
                type: 'array',
                items: {
                  type: 'object',
                  properties: {
                    email: { type: 'string', format: 'email' },
                    label: { type: 'string' }
                  },
                  required: ['email']
                }
              },
              organization: {
                type: 'object',
                properties: {
                  company: { type: 'string' },
                  title: { type: 'string' }
                }
              }
            },
            required: ['displayName', 'phones']
          }
        }
      },
      required: ['contacts']
    },
    InteractiveContent: {
      type: 'object',
      properties: {
        interactiveType: {
          type: 'string',
          enum: ['BUTTONS', 'LIST']
        },
        bodyText: {
          type: 'string',
          minLength: 1
        },
        footerText: { type: 'string' },
        actions: {
          oneOf: [
            { $ref: '#/$defs/ButtonsActions' },
            { $ref: '#/$defs/ListActions' }
          ]
        }
      },
      required: ['interactiveType', 'bodyText', 'actions']
    },
    ButtonsActions: {
      type: 'object',
      properties: {
        buttons: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              actionId: { type: 'string', minLength: 1 },
              title: { type: 'string', minLength: 1 },
              payload: { type: 'object' },
              kind: {
                type: 'string',
                enum: ['REPLY', 'URL', 'CALL']
              },
              url: { type: 'string', format: 'uri' },
              phone: { type: 'string' }
            },
            required: ['actionId', 'title', 'kind']
          }
        }
      },
      required: ['buttons']
    },
    ListActions: {
      type: 'object',
      properties: {
        buttonTitle: { type: 'string', minLength: 1 },
        sections: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              title: { type: 'string' },
              items: {
                type: 'array',
                items: {
                  type: 'object',
                  properties: {
                    actionId: { type: 'string', minLength: 1 },
                    title: { type: 'string', minLength: 1 },
                    description: { type: 'string' },
                    payload: { type: 'object' }
                  },
                  required: ['actionId', 'title']
                }
              }
            },
            required: ['items']
          }
        }
      },
      required: ['buttonTitle', 'sections']
    },
    ReactionContent: {
      type: 'object',
      properties: {
        targetMessageId: { type: 'string', minLength: 1 },
        reaction: { type: 'string', minLength: 1 }
      },
      required: ['targetMessageId', 'reaction']
    }
  }
};