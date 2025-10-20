import { createClient } from '@/lib/supabase/server'
import { NextRequest, NextResponse } from 'next/server'

export async function GET(request: NextRequest) {
  const { searchParams, origin } = new URL(request.url)
  const code = searchParams.get('code')
  const next = searchParams.get('next') ?? '/'
  const error = searchParams.get('error')
  const errorDescription = searchParams.get('error_description')

  // If there's already an error from the OAuth provider, redirect to error page
  if (error) {
    console.error('OAuth error:', error, errorDescription)
    return NextResponse.redirect(`${origin}/auth/auth-code-error?error=${error}&description=${errorDescription}`)
  }

  if (code) {
    const supabase = await createClient()
    const { data, error: authError } = await supabase.auth.exchangeCodeForSession(code)
    
    if (authError) {
      console.error('Supabase auth error:', authError)
      return NextResponse.redirect(`${origin}/auth/auth-code-error?error=auth_failed&description=${encodeURIComponent(authError.message)}`)
    }
    
    if (data?.user) {
      // Successfully authenticated
      return NextResponse.redirect(`${origin}${next}`)
    }
  }

  // No code provided or other issue
  return NextResponse.redirect(`${origin}/auth/auth-code-error?error=missing_code`)
}