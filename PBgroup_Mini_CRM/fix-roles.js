
const fs = require('fs');
const path = require('path');

function walk(dir, callback) {
    const files = fs.readdirSync(dir);
    files.forEach(file => {
        const filepath = path.join(dir, file);
        const stats = fs.statSync(filepath);
        if (stats.isDirectory()) {
            walk(filepath, callback);
        } else if (stats.isFile()) {
            callback(filepath);
        }
    });
}

function replaceInFile(filepath) {
    if (!filepath.endsWith('.ts') && !filepath.endsWith('.tsx')) return;

    let content = fs.readFileSync(filepath, 'utf8');
    let original = content;

    // Existing Enum replacements
    content = content.replace(/Role\.MANAGER/g, 'Role.ADMIN_STAFF');
    content = content.replace(/Role\.EDITOR/g, 'Role.TARGETOLOGIST');
    content = content.replace(/Role\.VIEWER/g, 'Role.SALES');

    // String literal replacements (including single and double quotes)
    // Be careful not to replace partial words, but roles are usually distinct uppercase.
    content = content.replace(/'MANAGER'/g, "'ADMIN_STAFF'");
    content = content.replace(/"MANAGER"/g, '"ADMIN_STAFF"');

    content = content.replace(/'EDITOR'/g, "'TARGETOLOGIST'");
    content = content.replace(/"EDITOR"/g, '"TARGETOLOGIST"');

    content = content.replace(/'VIEWER'/g, "'SALES'");
    content = content.replace(/"VIEWER"/g, '"SALES"');

    if (content !== original) {
        console.log('Updating:', filepath);
        fs.writeFileSync(filepath, content, 'utf8');
    }
}

walk('./src', replaceInFile);
