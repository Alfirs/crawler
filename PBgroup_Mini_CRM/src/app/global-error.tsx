"use client"

export default function GlobalError({
    error,
    reset,
}: {
    error: Error & { digest?: string }
    reset: () => void
}) {
    return (
        <html>
            <body>
                <div className="flex min-h-screen flex-col items-center justify-center">
                    <h2>Something went wrong!</h2>
                    <p className="mb-4 text-red-500">{error.message}</p>
                    <button
                        onClick={() => reset()}
                        className="rounded bg-blue-500 px-4 py-2 text-white hover:bg-blue-600"
                    >
                        Try again
                    </button>
                </div>
            </body>
        </html>
    )
}
