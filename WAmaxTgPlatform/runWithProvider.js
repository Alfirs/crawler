const { execSync } = require('child_process');

const provider = process.env.DATABASE_PROVIDER || 'postgresql';
const args = process.argv.slice(2);
const command = args.join(' ');

if (!command) {
  console.error('No command provided to runWithProvider.js');
  process.exit(1);
}

const resolvedCommand = command.replace(/DATABASE_PROVIDER/g, provider);

try {
  execSync(resolvedCommand, { stdio: 'inherit', shell: true });
} catch (error) {
  console.error('Command failed:', resolvedCommand);
  process.exit(1);
}
