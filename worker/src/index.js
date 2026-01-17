/**
 * Telegram Brain v2 - Serverless Worker
 *
 * Endpoints:
 * - POST /webhook - Telegram webhook handler
 * - GET /health - Health check
 * - POST /sync - Trigger vault sync from GitHub (called by GitHub Action)
 */

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    try {
      // Health check - deep verification
      if (url.pathname === '/health') {
        const checks = {
          gemini: !!env.GEMINI_API_KEY,
          telegram: !!env.TELEGRAM_BOT_TOKEN,
        };

        // Check vault context file exists and has content
        try {
          const contextFile = await env.VAULT.get('_vault_context.md');
          if (contextFile) {
            const content = await contextFile.text();
            checks.vault = {
              ok: content.length > 1000,
              sizeKB: Math.round(content.length / 1024),
            };
          } else {
            checks.vault = { ok: false, error: 'No context file' };
          }
        } catch (e) {
          checks.vault = { ok: false, error: e.message };
        }

        const allOk = checks.gemini && checks.telegram && checks.vault?.ok;

        return jsonResponse({
          status: allOk ? 'healthy' : 'degraded',
          checks,
          timestamp: new Date().toISOString(),
        });
      }

      // Telegram webhook
      if (url.pathname === '/webhook' && request.method === 'POST') {
        // Validate Telegram webhook secret (if configured)
        if (env.WEBHOOK_SECRET) {
          const secretHeader = request.headers.get('X-Telegram-Bot-Api-Secret-Token');
          if (secretHeader !== env.WEBHOOK_SECRET) {
            console.log('Webhook auth failed: invalid or missing secret token');
            return jsonResponse({ error: 'Unauthorized' }, 401);
          }
        }

        const update = await request.json();
        ctx.waitUntil(handleTelegramUpdate(update, env));
        return jsonResponse({ ok: true });
      }

      // GitHub sync endpoint (webhook from GitHub Action)
      if (url.pathname === '/sync' && request.method === 'POST') {
        // Optional: verify GitHub webhook signature
        const result = await syncVaultFromGitHub(env);
        return jsonResponse(result);
      }

      // Export captures endpoint - list all telegram captures in R2
      if (url.pathname === '/captures/export') {
        const captures = await exportCaptures(env);
        return jsonResponse(captures);
      }

      return jsonResponse({ error: 'Not found' }, 404);
    } catch (error) {
      console.error('Worker error:', error);
      return jsonResponse({ error: error.message }, 500);
    }
  },
};

function jsonResponse(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

/**
 * Handle incoming Telegram update
 */
async function handleTelegramUpdate(update, env) {
  console.log('Received update:', JSON.stringify(update).substring(0, 200));

  const message = update.message;
  if (!message || !message.text) {
    console.log('No message or text, skipping');
    return;
  }

  const chatId = message.chat.id;
  const userId = message.from.id;
  const text = message.text;

  // Auth check - only allow configured user
  if (env.ALLOWED_USER_ID && userId.toString() !== env.ALLOWED_USER_ID) {
    await sendTelegram(env, chatId, '⛔ Unauthorized');
    return;
  }

  // Command routing
  if (text.startsWith('/ask ')) {
    const query = text.slice(5).trim();
    await handleAskCommand(env, chatId, message.message_id, query);
  } else if (text === '/help' || text === '/start') {
    await handleHelpCommand(env, chatId);
  } else if (text === '/recent') {
    await handleRecentCommand(env, chatId);
  } else if (text === '/stats') {
    await handleStatsCommand(env, chatId);
  } else if (text === '/health') {
    await sendTelegram(env, chatId, '✅ Bot is running');
  } else if (text.startsWith('/')) {
    // Unknown command
    await sendTelegram(env, chatId, `Unknown command. Try /help`);
  } else {
    // Default: capture to inbox
    await handleCapture(env, chatId, message.message_id, text);
  }
}

/**
 * Capture message to R2 inbox
 */
async function handleCapture(env, chatId, messageId, text) {
  console.log(`Capture: chatId=${chatId}, messageId=${messageId}, text=${text.substring(0, 50)}`);
  try {
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    const filename = `0-Inbox/telegram-${timestamp}.md`;
    console.log(`Writing to R2: ${filename}`);

    const content = `#telegram #capture

${text}

---
*Captured via Telegram: ${new Date().toISOString()}*
`;

    await env.VAULT.put(filename, content, {
      httpMetadata: { contentType: 'text/markdown' },
    });

    // Confirm capture with reaction (thumbs up) and silent message
    await reactToMessage(env, chatId, messageId, '👍');
  } catch (error) {
    console.error('Capture error:', error);
    await sendTelegram(env, chatId, `❌ Capture failed: ${error.message}`);
  }
}

/**
 * Handle /help command - list available commands
 */
async function handleHelpCommand(env, chatId) {
  const help = `*Second Brain Bot*

📝 *Capture* - Just send any text
/ask <query> - Query your vault
/recent - Show recent captures
/stats - Vault statistics
/health - Check bot status
/help - This message

_Tip: Send links, ideas, or notes - they're saved to your inbox for processing._`;

  await sendTelegram(env, chatId, help);
}

/**
 * Handle /recent command - show recent inbox captures
 */
async function handleRecentCommand(env, chatId) {
  try {
    // List objects in 0-Inbox/ prefix
    const listed = await env.VAULT.list({ prefix: '0-Inbox/', limit: 10 });

    if (!listed.objects || listed.objects.length === 0) {
      await sendTelegram(env, chatId, '_📭 Inbox empty_');
      return;
    }

    // Sort by uploaded time (most recent first) and take 5
    const sorted = listed.objects
      .sort((a, b) => new Date(b.uploaded) - new Date(a.uploaded))
      .slice(0, 5);

    // Build response
    let response = '*📬 Recent Captures*\n\n';

    for (const obj of sorted) {
      // Get first line of content as preview
      const file = await env.VAULT.get(obj.key);
      if (file) {
        const content = await file.text();
        // Skip tags, get first meaningful line
        const lines = content.split('\n').filter(l => l.trim() && !l.startsWith('#'));
        const preview = lines[0]?.substring(0, 60) || '(empty)';
        const truncated = preview.length >= 60 ? preview + '...' : preview;

        // Parse timestamp from filename: telegram-2026-01-14T21-21-46-819Z.md
        const match = obj.key.match(/telegram-(\d{4}-\d{2}-\d{2})T(\d{2})-(\d{2})/);
        const dateStr = match ? `${match[1]} ${match[2]}:${match[3]}` : 'unknown';

        response += `• _${dateStr}_\n${truncated}\n\n`;
      }
    }

    response += `_${listed.objects.length} total in inbox_`;
    await sendTelegram(env, chatId, response);
  } catch (error) {
    console.error('Recent error:', error);
    await sendTelegram(env, chatId, `❌ ${error.message}`);
  }
}

/**
 * Handle /stats command - show vault statistics
 */
async function handleStatsCommand(env, chatId) {
  try {
    // Get vault context size
    const contextFile = await env.VAULT.get('_vault_context.md');
    let vaultInfo = 'Not synced';
    let fileCount = 0;

    if (contextFile) {
      const content = await contextFile.text();
      const sizeKB = Math.round(content.length / 1024);

      // Count files from context (each file starts with "## File: ")
      const matches = content.match(/^## File: /gm);
      fileCount = matches ? matches.length : 0;

      vaultInfo = `${sizeKB}KB · ${fileCount} files`;
    }

    // Count inbox items
    const inbox = await env.VAULT.list({ prefix: '0-Inbox/', limit: 100 });
    const inboxCount = inbox.objects?.length || 0;

    const stats = `*📊 Vault Stats*

📁 Context: ${vaultInfo}
📬 Inbox: ${inboxCount} captures
🤖 Model: ${env.MODEL || 'gemini-2.5-flash-lite'}

_Run sync-vault.sh to update context_`;

    await sendTelegram(env, chatId, stats);
  } catch (error) {
    console.error('Stats error:', error);
    await sendTelegram(env, chatId, `❌ ${error.message}`);
  }
}

/**
 * Export all Telegram captures from R2
 * Returns JSON with all capture files and their content
 */
async function exportCaptures(env) {
  try {
    // List all telegram captures in inbox
    const listed = await env.VAULT.list({ prefix: '0-Inbox/telegram-', limit: 1000 });

    if (!listed.objects || listed.objects.length === 0) {
      return { captures: [], count: 0 };
    }

    // Get content of each capture
    const captures = [];
    for (const obj of listed.objects) {
      const file = await env.VAULT.get(obj.key);
      if (file) {
        const content = await file.text();
        captures.push({
          key: obj.key,
          filename: obj.key.split('/').pop(),
          uploaded: obj.uploaded,
          content: content,
        });
      }
    }

    return {
      captures: captures,
      count: captures.length,
      exported_at: new Date().toISOString(),
    };
  } catch (error) {
    console.error('Export error:', error);
    return { error: error.message };
  }
}

/**
 * Handle /ask query - load vault, query Gemini (with timeout protection)
 */
async function handleAskCommand(env, chatId, messageId, query) {
  const TIMEOUT_MS = 25000; // 25s timeout (CF limit is 30s)
  const startTime = Date.now();

  const timeoutPromise = new Promise((_, reject) => {
    setTimeout(() => reject(new Error('TIMEOUT')), TIMEOUT_MS);
  });

  try {
    // Send typing indicator
    await sendChatAction(env, chatId, 'typing');

    // Race against timeout
    const { answer, vaultSizeKB } = await Promise.race([
      (async () => {
        const { content, sizeKB } = await loadVaultFromR2(env);
        if (!content) {
          throw new Error('Vault empty - run sync first');
        }
        const answer = await queryGemini(env, content, query);
        return { answer, vaultSizeKB: sizeKB };
      })(),
      timeoutPromise,
    ]);

    // Add minimal footer with response time and vault size
    const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
    const response = `${answer}\n\n_⚡ ${elapsed}s · ${vaultSizeKB}KB vault_`;

    await sendTelegram(env, chatId, response, { reply_to_message_id: messageId });
  } catch (error) {
    console.error('Ask error:', error);
    const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);

    if (error.message === 'TIMEOUT') {
      await sendTelegram(env, chatId, `⏱️ Query timed out after ${elapsed}s. Try a simpler question.`);
    } else {
      await sendTelegram(env, chatId, `❌ ${error.message}\n\n_⚡ ${elapsed}s_`);
    }
  }
}

/**
 * Load pre-aggregated vault context from R2 (single file, fast)
 * Returns { content, sizeKB } or { content: null, sizeKB: 0 }
 */
async function loadVaultFromR2(env) {
  console.log('Loading vault context from R2...');

  try {
    // Load single pre-aggregated context file
    const contextFile = await env.VAULT.get('_vault_context.md');

    if (!contextFile) {
      console.error('No _vault_context.md found - run sync-vault.sh first');
      return { content: null, sizeKB: 0 };
    }

    const content = await contextFile.text();
    const sizeKB = Math.round(content.length / 1024);
    console.log(`Loaded vault context (${sizeKB}KB)`);

    return { content, sizeKB };
  } catch (error) {
    console.error('Failed to load vault context:', error);
    return { content: null, sizeKB: 0 };
  }
}

/**
 * Query Gemini with vault context
 */
async function queryGemini(env, vaultContent, query) {
  const model = env.MODEL || 'gemini-2.5-flash-lite';
  const apiKey = env.GEMINI_API_KEY;

  if (!apiKey) {
    throw new Error('GEMINI_API_KEY not configured');
  }

  const prompt = `You are a helpful assistant with access to a personal knowledge vault.

Here is the vault content:

${vaultContent}

---

Based on the vault content above, answer this question:
${query}

Be concise and specific. If you can't find relevant information in the vault, say so.
Cite which files you found the information in when relevant.`;

  const response = await fetch(
    `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${apiKey}`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        contents: [{ parts: [{ text: prompt }] }],
        generationConfig: {
          maxOutputTokens: 1024,
          temperature: 0.7,
        },
      }),
    }
  );

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`Gemini API error: ${error}`);
  }

  const data = await response.json();

  // Extract response text
  const text = data.candidates?.[0]?.content?.parts?.[0]?.text;
  if (!text) {
    throw new Error('No response from Gemini');
  }

  return text;
}

/**
 * Sync vault from GitHub (placeholder - implement based on your needs)
 */
async function syncVaultFromGitHub(env) {
  // This would be called by a GitHub Action after push
  // The Action would use R2 API to upload changed files
  return {
    status: 'ok',
    message: 'Sync endpoint ready. Configure GitHub Action to push to R2.',
  };
}

// Telegram API helpers
async function sendTelegram(env, chatId, text, options = {}) {
  const url = `https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`;
  await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      chat_id: chatId,
      text: text,
      parse_mode: 'Markdown',
      ...options,
    }),
  });
}

async function reactToMessage(env, chatId, messageId, emoji) {
  // Map common emojis to Telegram-supported reaction emojis
  const emojiMap = {
    '✅': '👍',
    '❌': '👎',
  };
  const mappedEmoji = emojiMap[emoji] || emoji;

  const url = `https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/setMessageReaction`;
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      chat_id: chatId,
      message_id: messageId,
      reaction: [{ type: 'emoji', emoji: mappedEmoji }],
    }),
  });

  if (!response.ok) {
    console.error('Reaction failed:', await response.text());
  }
}

async function sendChatAction(env, chatId, action) {
  const url = `https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendChatAction`;
  await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      chat_id: chatId,
      action: action,
    }),
  });
}
