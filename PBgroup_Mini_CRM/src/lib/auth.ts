import { NextAuthOptions } from "next-auth"
import CredentialsProvider from "next-auth/providers/credentials"
import { prisma } from "@/lib/prisma"
import { compare } from "bcryptjs"
import { logAudit } from "@/lib/audit"

export const authOptions: NextAuthOptions = {
    providers: [
        CredentialsProvider({
            name: "Credentials",
            credentials: {
                login: { label: "Login", type: "text" },
                password: { label: "Password", type: "password" },
            },
            async authorize(credentials) {
                if (!credentials?.login || !credentials?.password) return null

                const user = await prisma.user.findUnique({
                    where: { login: credentials.login },
                })

                if (!user) return null

                const isPasswordValid = await compare(credentials.password, user.passwordHash)

                if (!isPasswordValid) return null

                return {
                    id: user.id,
                    name: user.fullName,
                    email: user.login,
                    role: user.role,
                }
            },
        }),
    ],
    callbacks: {
        async jwt({ token, user }) {
            if (user) {
                token.id = user.id
                token.role = (user as any).role
            }
            return token
        },
        async session({ session, token }) {
            if (session.user) {
                (session.user as any).id = token.id;
                (session.user as any).role = token.role
            }
            return session
        },
    },
    events: {
        async signIn({ user }) {
            await logAudit({
                userId: user.id,
                action: "LOGIN",
                entityType: "AUTH",
                entityId: user.id,
            })
        }
    },
    pages: {
        signIn: "/login",
    },
    session: {
        strategy: "jwt"
    },
    secret: process.env.NEXTAUTH_SECRET,
}
