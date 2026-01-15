/**
 * Phase 0 - Test 1: Cloudflare Worker Limits
 *
 * Tests whether a CF Worker can make a 2-5s external API call to Gemini.
 *
 * Free tier limits:
 * - 10ms CPU time (but async I/O doesn't count against this)
 * - 30s total request timeout
 * - 100k requests/day
 */

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    // Health check endpoint
    if (url.pathname === '/health') {
      return new Response(JSON.stringify({
        status: 'ok',
        timestamp: new Date().toISOString(),
        hasApiKey: !!env.GEMINI_API_KEY,
      }), {
        headers: { 'Content-Type': 'application/json' }
      });
    }

    // Main test endpoint
    if (url.pathname === '/test') {
      return await testGeminiCall(env);
    }

    // Large context test
    if (url.pathname === '/test-large') {
      return await testLargeContext(env);
    }

    return new Response(JSON.stringify({
      message: 'CF Worker Limit Test',
      endpoints: {
        '/health': 'Health check',
        '/test': 'Small Gemini API call (quick)',
        '/test-large': 'Large context test (~250k tokens)',
      }
    }), {
      headers: { 'Content-Type': 'application/json' }
    });
  },
};

async function testGeminiCall(env) {
  const startTime = Date.now();

  if (!env.GEMINI_API_KEY) {
    return new Response(JSON.stringify({
      error: 'GEMINI_API_KEY not configured',
      hint: 'Run: wrangler secret put GEMINI_API_KEY',
    }), { status: 500, headers: { 'Content-Type': 'application/json' } });
  }

  try {
    const apiUrl = `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-lite:generateContent?key=${env.GEMINI_API_KEY}`;

    const response = await fetch(apiUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        contents: [{
          parts: [{ text: 'Say "Hello from Cloudflare Worker!" in exactly 10 words.' }]
        }]
      }),
    });

    const elapsed = Date.now() - startTime;

    if (!response.ok) {
      const error = await response.text();
      return new Response(JSON.stringify({
        success: false,
        elapsed_ms: elapsed,
        status: response.status,
        error: error,
      }), { status: 500, headers: { 'Content-Type': 'application/json' } });
    }

    const data = await response.json();
    const text = data.candidates?.[0]?.content?.parts?.[0]?.text || 'No response';

    return new Response(JSON.stringify({
      success: true,
      elapsed_ms: elapsed,
      response: text,
      usage: data.usageMetadata,
      verdict: elapsed < 30000 ? 'PASS: Within 30s limit' : 'WARN: Close to limit',
    }), { headers: { 'Content-Type': 'application/json' } });

  } catch (error) {
    const elapsed = Date.now() - startTime;
    return new Response(JSON.stringify({
      success: false,
      elapsed_ms: elapsed,
      error: error.message,
    }), { status: 500, headers: { 'Content-Type': 'application/json' } });
  }
}

async function testLargeContext(env) {
  const startTime = Date.now();

  if (!env.GEMINI_API_KEY) {
    return new Response(JSON.stringify({
      error: 'GEMINI_API_KEY not configured',
    }), { status: 500, headers: { 'Content-Type': 'application/json' } });
  }

  // Generate ~250k tokens of content (similar to vault size)
  // Each word is roughly 1.3 tokens, so we need ~200k words
  // For testing, we'll use repeated content pattern
  const paragraph = `This is a test paragraph that simulates vault content. It contains information about various topics including technology, business, and personal notes. The content is repeated to reach approximately 250,000 tokens which matches the expected vault size. `;

  // Repeat to get ~250k tokens (~1M characters / 4 chars per token)
  const largeContent = paragraph.repeat(4000); // ~250k tokens

  try {
    const apiUrl = `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-lite:generateContent?key=${env.GEMINI_API_KEY}`;

    const response = await fetch(apiUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        contents: [{
          parts: [{
            text: `${largeContent}\n\nBased on the content above, summarize the main topic in one sentence.`
          }]
        }]
      }),
    });

    const elapsed = Date.now() - startTime;

    if (!response.ok) {
      const error = await response.text();
      return new Response(JSON.stringify({
        success: false,
        elapsed_ms: elapsed,
        status: response.status,
        error: error,
        content_size_chars: largeContent.length,
      }), { status: 500, headers: { 'Content-Type': 'application/json' } });
    }

    const data = await response.json();
    const text = data.candidates?.[0]?.content?.parts?.[0]?.text || 'No response';

    return new Response(JSON.stringify({
      success: true,
      elapsed_ms: elapsed,
      response: text,
      usage: data.usageMetadata,
      content_size_chars: largeContent.length,
      estimated_tokens: Math.round(largeContent.length / 4),
      verdict: elapsed < 30000 ? 'PASS: Large context within 30s' : 'WARN: Close to limit',
    }), { headers: { 'Content-Type': 'application/json' } });

  } catch (error) {
    const elapsed = Date.now() - startTime;
    return new Response(JSON.stringify({
      success: false,
      elapsed_ms: elapsed,
      error: error.message,
      content_size_chars: largeContent?.length || 0,
    }), { status: 500, headers: { 'Content-Type': 'application/json' } });
  }
}
