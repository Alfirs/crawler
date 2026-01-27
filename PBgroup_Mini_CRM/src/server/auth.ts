import { NextAuthOptions, getServerSession } from "next-auth"
import CredentialsProvider from "next-auth/providers/credentials"
import { db } from "@/lib/db"
import { compare } from "bcryptjs"
import { Role } from "@prisma/client"

export const authOptions: NextAuthOptions = {
    providers: [
        CredentialsProvider({
            name: "Credentials",
            credentials: {
                login: { label: "Login", type: "text" },
                password: { label: "Password", type: "password" },
            },
            async authorize(credentials) {
                if (!credentials?.login || !credentials?.password) {
                    throw new Error("Missing credentials")
                }

                const user = await db.user.findUnique({
                    where: { login: credentials.login },
                })

                if (!user || user.deletedAt) {
                    throw new Error("Invalid credentials")
                }

                const isValid = await compare(credentials.password, user.passwordHash)

                if (!isValid) {
                    throw new Error("Invalid credentials")
                }

                return {
                    id: user.id,
                    name: user.fullName,
                    email: user.login, // using login as email for NextAuth compatibility
                    role: user.role,
                }
            },
        }),
    ],
    callbacks: {
        async jwt({ token, user }) {
            if (user) {
                token.id = user.id
                token.role = user.role
            }
            return token
        },
        async session({ session, token }) {
            if (token) {
                session.user.id = token.id as string
                session.user.role = token.role as Role
                session.user.name = token.name
            }
            return session
        },
    },
    pages: {
        signIn: "/login",
    },
    session: {
        strategy: "jwt",
    },
}

export const getServerAuthSession = () => getServerSession(authOptions)
