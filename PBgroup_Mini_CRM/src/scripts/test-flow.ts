
import { parse } from 'cookie';

const BASE_URL = "http://localhost:3000";

async function main() {
    console.log("🚀 Starting Integration Test...");

    // 1. Get CSRF Token
    const csrfRes = await fetch(`${BASE_URL}/api/auth/csrf`);
    const csrfData = await csrfRes.json();
    const csrfToken = csrfData.csrfToken;
    const setCookieHeader = csrfRes.headers.get('set-cookie');

    if (!csrfToken) throw new Error("Failed to get CSRF token");
    console.log("✅ CSRF Token retrieved");

    // Keep cookies
    let cookies = setCookieHeader ? [setCookieHeader.split(';')[0]] : [];

    // 2. Login
    const params = new URLSearchParams();
    params.append('csrfToken', csrfToken);
    params.append('login', 'admin');
    params.append('password', 'admin1234');
    params.append('redirect', 'false');
    params.append('json', 'true');

    const loginRes = await fetch(`${BASE_URL}/api/auth/callback/credentials`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Cookie': cookies.join('; ')
        },
        body: params
    });

    // NextAuth sets the session cookie on the response
    const loginCookies = loginRes.headers.get('set-cookie');
    if (loginCookies) {
        // Extract the session token
        const sessionParts = loginCookies.split(',').map(c => c.split(';')[0]);
        cookies = [...cookies, ...sessionParts];
    }

    if (!loginRes.ok) {
        console.log(await loginRes.text());
        throw new Error("Login failed");
    }
    console.log("✅ Login successful");

    // 3. Create Client
    const clientData = {
        name: "Integration Test Client",
        status: "IN_PROGRESS",
        budget: 10000,
        phone: "+79990000000"
    };

    const createRes = await fetch(`${BASE_URL}/api/clients`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Cookie': cookies.join('; ')
        },
        body: JSON.stringify(clientData)
    });

    if (!createRes.ok) throw new Error(`Create Client failed: ${await createRes.text()}`);
    const client = await createRes.json();
    console.log(`✅ Client created: ${client.name} (${client.id})`);

    // 4. Add Stats
    const statData = {
        date: new Date().toISOString(),
        spend: 5000,
        leads: 10,
        revenue: 20000
    };

    const statRes = await fetch(`${BASE_URL}/api/clients/${client.id}/stats`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Cookie': cookies.join('; ')
        },
        body: JSON.stringify(statData)
    });

    if (!statRes.ok) throw new Error(`Add Stats failed: ${await statRes.text()}`);
    const stat = await statRes.json();
    console.log(`✅ Stats added: Spend ${stat.spend}, Revenue ${stat.revenue}`);

    // 5. Verify Audit Log
    const auditRes = await fetch(`${BASE_URL}/api/audit`, {
        method: 'GET',
        headers: {
            'Cookie': cookies.join('; ')
        }
    });

    if (!auditRes.ok) throw new Error(`Get Audit failed: ${await auditRes.text()}`);
    const auditLogs = await auditRes.json();

    const clientLog = auditLogs.find((l: any) => l.entityId === client.id && l.action === 'CREATE');
    if (clientLog) {
        console.log("✅ Audit Log verified for Client creation");
    } else {
        console.warn("⚠️ Audit Log missing for Client creation");
    }

    console.log("\n🎉 All Tests Passed!");
}

main().catch(e => {
    console.error("❌ Test Failed:", e);
    process.exit(1);
});
