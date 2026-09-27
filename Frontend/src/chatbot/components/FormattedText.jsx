import React from 'react';

/**
 * Parses inline formatting:
 * - Bold: **text**, ** text **, __text__
 * - Italic: *text*, _text_
 * - Inline code: `code`
 * - Strikethrough: ~~text~~
 * - Links: [label](url)
 */
export const formatInlineText = (text) => {
  if (!text || typeof text !== 'string') return text;

  // Regex to match inline tokens
  const tokenRegex = /(`[^`\n]+`|\[[^\]]+\]\([^\)]+\)|\*\*[^*]+?\*\*|__[^_]+?__|~~[^~]+?~~|(?<!\*)\*[^*\n]+?\*(?!\*)|(?<!_)_[^_\n]+?_(?!_))/g;

  const parts = [];
  let lastIndex = 0;
  let match;

  while ((match = tokenRegex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.substring(lastIndex, match.index));
    }

    const token = match[0];
    const key = `inline-${match.index}`;

    // 1. Inline Code: `...`
    if (token.startsWith('`') && token.endsWith('`') && token.length >= 2) {
      parts.push(
        <code key={key} className="cb-inline-code">
          {token.slice(1, -1)}
        </code>
      );
    }
    // 2. Links: [text](url)
    else if (token.startsWith('[') && token.includes('](') && token.endsWith(')')) {
      const linkText = token.substring(1, token.indexOf(']('));
      const linkUrl = token.substring(token.indexOf('](') + 2, token.length - 1);
      parts.push(
        <a
          key={key}
          href={linkUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="cb-message-link"
        >
          {linkText}
        </a>
      );
    }
    // 3. Bold: **...** or __...__ (handles spaces inside like ** text **)
    else if (
      (token.startsWith('**') && token.endsWith('**') && token.length >= 4) ||
      (token.startsWith('__') && token.endsWith('__') && token.length >= 4)
    ) {
      const rawInner = token.slice(2, -2).trim();
      parts.push(
        <strong key={key} className="cb-strong-text">
          {formatInlineText(rawInner)}
        </strong>
      );
    }
    // 4. Strikethrough: ~~...~~
    else if (token.startsWith('~~') && token.endsWith('~~') && token.length >= 4) {
      const rawInner = token.slice(2, -2).trim();
      parts.push(
        <del key={key} className="cb-del-text">
          {formatInlineText(rawInner)}
        </del>
      );
    }
    // 5. Italic: *...* or _..._
    else if (
      (token.startsWith('*') && token.endsWith('*') && token.length >= 2) ||
      (token.startsWith('_') && token.endsWith('_') && token.length >= 2)
    ) {
      const rawInner = token.slice(1, -1).trim();
      parts.push(
        <em key={key} className="cb-em-text">
          {formatInlineText(rawInner)}
        </em>
      );
    } else {
      parts.push(token);
    }

    lastIndex = tokenRegex.lastIndex;
  }

  if (lastIndex < text.length) {
    parts.push(text.substring(lastIndex));
  }

  return parts.length === 0 ? text : parts;
};

/**
 * FormattedText Component
 * Renders full markdown-style formatting with blocks, headings, lists, code, and bold text.
 */
export const FormattedText = ({ text, className = '' }) => {
  if (!text || typeof text !== 'string') return null;

  // Split out fenced code blocks: ```lang ... ```
  const codeBlockRegex = /```([a-zA-Z0-9_-]*)\n([\s\S]*?)```/g;
  const blocks = [];
  let lastIdx = 0;
  let codeMatch;

  while ((codeMatch = codeBlockRegex.exec(text)) !== null) {
    if (codeMatch.index > lastIdx) {
      blocks.push({ type: 'text', content: text.substring(lastIdx, codeMatch.index) });
    }
    blocks.push({
      type: 'code',
      lang: codeMatch[1],
      content: codeMatch[2]
    });
    lastIdx = codeBlockRegex.lastIndex;
  }
  if (lastIdx < text.length) {
    blocks.push({ type: 'text', content: text.substring(lastIdx) });
  }

  return (
    <div className={`cb-formatted-text ${className}`}>
      {blocks.map((block, bIdx) => {
        if (block.type === 'code') {
          return (
            <div key={`code-block-${bIdx}`} className="cb-code-block-wrap">
              {block.lang && <span className="cb-code-lang">{block.lang}</span>}
              <pre className="cb-code-block">
                <code>{block.content}</code>
              </pre>
            </div>
          );
        }

        // Process text block: parse line by line
        const lines = block.content.split('\n');
        const elements = [];
        let listItems = [];
        let listType = null; // 'ul' | 'ol'

        const flushList = (keySuffix) => {
          if (listItems.length > 0) {
            const listKey = `list-${bIdx}-${keySuffix}`;
            if (listType === 'ol') {
              elements.push(
                <ol key={listKey} className="cb-message-ol">
                  {listItems.map((item, i) => (
                    <li key={i}>{formatInlineText(item)}</li>
                  ))}
                </ol>
              );
            } else {
              elements.push(
                <ul key={listKey} className="cb-message-ul">
                  {listItems.map((item, i) => (
                    <li key={i}>{formatInlineText(item)}</li>
                  ))}
                </ul>
              );
            }
            listItems = [];
            listType = null;
          }
        };

        lines.forEach((line, lIdx) => {
          const trimmed = line.trim();

          // Horizontal rule
          if (trimmed === '---' || trimmed === '***' || trimmed === '___') {
            flushList(lIdx);
            elements.push(<hr key={`hr-${bIdx}-${lIdx}`} className="cb-message-hr" />);
          }
          // Blockquote
          else if (trimmed.startsWith('> ')) {
            flushList(lIdx);
            elements.push(
              <blockquote key={`quote-${bIdx}-${lIdx}`} className="cb-message-quote">
                {formatInlineText(trimmed.substring(2))}
              </blockquote>
            );
          }
          // Headings
          else if (trimmed.startsWith('#### ')) {
            flushList(lIdx);
            elements.push(
              <h5 key={`h4-${bIdx}-${lIdx}`} className="cb-message-h4">
                {formatInlineText(trimmed.substring(5))}
              </h5>
            );
          } else if (trimmed.startsWith('### ')) {
            flushList(lIdx);
            elements.push(
              <h4 key={`h3-${bIdx}-${lIdx}`} className="cb-message-h3">
                {formatInlineText(trimmed.substring(4))}
              </h4>
            );
          } else if (trimmed.startsWith('## ')) {
            flushList(lIdx);
            elements.push(
              <h3 key={`h2-${bIdx}-${lIdx}`} className="cb-message-h2">
                {formatInlineText(trimmed.substring(3))}
              </h3>
            );
          } else if (trimmed.startsWith('# ')) {
            flushList(lIdx);
            elements.push(
              <h2 key={`h1-${bIdx}-${lIdx}`} className="cb-message-h1">
                {formatInlineText(trimmed.substring(2))}
              </h2>
            );
          }
          // Unordered list items: -, *, •
          else if (/^[-*•]\s+/.test(trimmed)) {
            const content = trimmed.replace(/^[-*•]\s+/, '');
            if (listType && listType !== 'ul') {
              flushList(lIdx);
            }
            listType = 'ul';
            listItems.push(content);
          }
          // Ordered list items: 1. 2.
          else if (/^\d+\.\s+/.test(trimmed)) {
            const content = trimmed.replace(/^\d+\.\s+/, '');
            if (listType && listType !== 'ol') {
              flushList(lIdx);
            }
            listType = 'ol';
            listItems.push(content);
          }
          // Empty line
          else if (!trimmed) {
            flushList(lIdx);
          }
          // Normal line of text
          else {
            flushList(lIdx);
            elements.push(
              <p key={`p-${bIdx}-${lIdx}`} className="cb-message-p">
                {formatInlineText(line)}
              </p>
            );
          }
        });

        flushList('end');

        return <React.Fragment key={`block-${bIdx}`}>{elements}</React.Fragment>;
      })}
    </div>
  );
};

export default FormattedText;
