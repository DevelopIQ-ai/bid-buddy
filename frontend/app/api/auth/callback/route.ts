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
      // Sync Google OAuth tokens to profiles table if available
      if (data.session?.provider_token) {
        try {
          const updateData: Record<string, string> = {
            google_access_token: data.session.provider_token,
            updated_at: new Date().toISOString()
          }
          if (data.session.provider_refresh_token) {
            updateData.google_refresh_token = data.session.provider_refresh_token
          }
          
          // Set token expiration (Google OAuth tokens typically expire in 1 hour)
          if (data.session.expires_at) {
            // Use the session expiration time for the token
            updateData.google_token_expires_at = new Date(data.session.expires_at * 1000).toISOString()
          }
          
          // Update the profiles table with the new tokens
          await supabase
            .from('profiles')
            .upsert({
              id: data.user.id,
              email: data.user.email,
              ...updateData
            }, {
              onConflict: 'id'
            })
            
          console.log('Successfully synced Google OAuth tokens to profiles table')
        } catch (error) {
          console.error('Failed to sync Google OAuth tokens to profiles:', error)
          // Don't fail the auth flow, just log the error
        }
      }
      
      // Successfully authenticated
      return NextResponse.redirect(`${origin}${next}`)
    }
  }

  // No code provided or other issue
  return NextResponse.redirect(`${origin}/auth/auth-code-error?error=missing_code`)
}