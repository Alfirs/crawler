import { withAuth } from "next-auth/middleware"

export default withAuth({
    pages: {
        signIn: "/login",
    },
})

export const config = {
    matcher: [
        "/clients/:path*",
        "/stats/:path*",
        "/employees/:path*",
        "/api/clients/:path*",
        "/api/stats/:path*",
        "/api/details/:path*",
        "/api/employees/:path*",
        "/api/audit/:path*",
        "/api/files/:path*",
    ],
}
