# PBgroup Mini CRM

Production-ready web application for team management, statistics tracking, and client details.
Built with Next.js 14, TailwindCSS, shadcn/ui, Prisma, and PostgreSQL.

## Features

- **Role-Based Access**:
  - **ADMIN/MANAGER**: Full access to all clients and employees.
  - **EDITOR**: Access ONLY to assigned clients.
- **Client Management**: Create, edit, status tracking.
- **Statistics**: Excel-like daily stats editable table with automatic formula calculations (ROI, ROMI, CPL).
- **Details**: Tabbed interface for Pains, Creatives, Audiences, etc.
- **File Uploads**: Secure file storage for creatives.
- **Audit Log**: Tracks all create/update/assign actions.

## Tech Stack

- **Framework**: Next.js 14 (App Router)
- **Database**: PostgreSQL
- **ORM**: Prisma
- **Auth**: NextAuth.js (Credentials)
- **UI**: TailwindCSS + shadcn/ui
- **Validation**: Zod
- **Forms**: React Hook Form

## Getting Started

### Prerequisites

- Docker & Docker Compose
- Node.js 18+ (for local dev)

### Quick Start (Docker)

1. **Clone the repository** (if you haven't yet)
2. **Start the stack**:
   ```bash
   docker-compose up -d --build
   ```
3. **Run Migrations & Seed**:
   ```bash
   # Enter the app container
   docker-compose exec app npx prisma migrate deploy
   docker-compose exec app npx prisma db seed
   ```
4. **Open Browser**:
   - URL: `http://localhost:3000`
   - **Admin Credentials**:
     - Login: `admin`
     - Password: `admin1234`

### Local Development

1. **Install Dependencies**:
   ```bash
   npm install
   ```
2. **Setup Database**:
   - Ensure PostgreSQL is running (e.g., via Docker `docker-compose up -d db`).
   - Update `.env` if needed.
3. **Run Migrations**:
   ```bash
   npx prisma migrate dev --name init
   npx prisma db seed
   ```
4. **Start Server**:
   ```bash
   npm run dev
   ```

## Folder Structure

- `/src/app`: Next.js App Router pages and API routes.
- `/src/components`: UI components (shadcn) and feature-specific components.
- `/src/lib`: Utilities, database client, validation schemas.
- `/src/server`: Server-side logic (auth, access control, audit logging).
- `/prisma`: Database schema and seed script.
- `/public/uploads`: Storage for uploaded creative files.

## Assumptions

- **File Storage**: Using local disk storage (`/public/uploads`) as requested. In a multi-container clustered env, this should be a shared volume or S3.
- **Deletes**: No UI for deletion is provided to strict "Prohibit deletion" requirement.
- **Formulas**: ROI/ROMI are calculated on the fly in the frontend table.
