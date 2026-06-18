"use client";

import { memo } from "react";
import ReactMarkdown from "react-markdown";
import type { Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import { cn } from "@/lib/utils";
import { Bot, User } from "lucide-react";
import type { ChatMessage } from "@/lib/types";

interface MessageBubbleProps {
  message: ChatMessage;
  compact?: boolean;
}

function MessageBubble({ message, compact = false }: MessageBubbleProps) {
  const isUser = message.role === "user";
  const isStreaming = message.isStreaming && !message.content;

  const markdownComponents: Components = {
    code({ className, children, ...props }) {
      const match = /language-(\w+)/.exec(className || "");
      const isInline = !match;

      if (!isInline) {
        return (
          <SyntaxHighlighter
            style={oneDark}
            language={match?.[1] || "text"}
            PreTag="div"
            className="!rounded-lg !text-xs !my-2 !bg-[#0a0a0f]"
            customStyle={{
              fontSize: compact ? "10px" : "12px",
            }}
          >
            {String(children).replace(/\n$/, "")}
          </SyntaxHighlighter>
        );
      }

      return (
        <code
          className="bg-white/10 rounded px-1 py-0.5 font-mono text-violet-300"
          style={{
            fontSize: compact ? "10px" : "12px",
          }}
          {...props}
        >
          {children}
        </code>
      );
    },

    p: ({ children }) => (
      <p className="leading-relaxed mb-2 last:mb-0 text-white/70">{children}</p>
    ),

    ul: ({ children }) => (
      <ul className="list-disc list-inside space-y-1 my-2 text-white/60 pl-1">
        {children}
      </ul>
    ),

    ol: ({ children }) => (
      <ol className="list-decimal list-inside space-y-1 my-2 text-white/60 pl-1">
        {children}
      </ol>
    ),

    li: ({ children }) => <li className="leading-relaxed">{children}</li>,

    h1: ({ children }) => (
      <h1 className="text-base font-semibold text-white/90 mt-3 mb-1.5 first:mt-0">
        {children}
      </h1>
    ),

    h2: ({ children }) => (
      <h2 className="text-sm font-semibold text-white/85 mt-3 mb-1 first:mt-0">
        {children}
      </h2>
    ),

    h3: ({ children }) => (
      <h3 className="text-sm font-medium text-white/80 mt-2 mb-1 first:mt-0">
        {children}
      </h3>
    ),

    strong: ({ children }) => (
      <strong className="font-semibold text-white/90">{children}</strong>
    ),

    em: ({ children }) => <em className="italic text-white/60">{children}</em>,

    blockquote: ({ children }) => (
      <blockquote className="border-l-2 border-violet-500/40 pl-3 my-2 text-white/40 italic">
        {children}
      </blockquote>
    ),

    table: ({ children }) => (
      <div className="overflow-x-auto my-2">
        <table className="w-full border border-white/10 rounded-lg overflow-hidden text-xs">
          {children}
        </table>
      </div>
    ),

    th: ({ children }) => (
      <th className="px-3 py-1.5 text-left bg-white/5 text-white/50 font-medium border-b border-white/10">
        {children}
      </th>
    ),

    td: ({ children }) => (
      <td className="px-3 py-1.5 text-white/40 border-b border-white/5">
        {children}
      </td>
    ),

    a: ({ children, href }) => (
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        className="text-violet-400 hover:text-violet-300 underline underline-offset-2 transition-colors"
      >
        {children}
      </a>
    ),

    hr: () => <hr className="border-white/10 my-3" />,
  };

  return (
    <div
      className={cn("flex gap-2.5", isUser ? "flex-row-reverse" : "flex-row")}
    >
      {/* Avatar */}
      <div
        className={cn(
          "rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5",
          compact ? "w-5 h-5" : "w-6 h-6",
          isUser ? "bg-violet-600" : "bg-[#1a1a28] border border-white/10",
        )}
      >
        {isUser ? (
          <User
            className={cn(compact ? "w-2.5 h-2.5" : "w-3 h-3", "text-white")}
          />
        ) : (
          <Bot
            className={cn(
              compact ? "w-2.5 h-2.5" : "w-3 h-3",
              "text-violet-400",
            )}
          />
        )}
      </div>

      {/* Bubble */}
      <div
        className={cn(
          "rounded-2xl px-3.5 py-2.5 max-w-[80%]",
          isUser
            ? "bg-violet-600 text-white rounded-tr-sm"
            : "bg-[#111118] border border-white/8 text-white/75 rounded-tl-sm",
        )}
      >
        {/* Typing indicator */}
        {isStreaming ? (
          <div className="flex items-center gap-1 py-1">
            {[0, 150, 300].map((delay) => (
              <span
                key={delay}
                className="w-1.5 h-1.5 rounded-full bg-violet-400/60 animate-bounce"
                style={{ animationDelay: `${delay}ms` }}
              />
            ))}
          </div>
        ) : isUser ? (
          /* Plain text for user messages */
          <p
            className={cn(
              "leading-relaxed whitespace-pre-wrap",
              compact ? "text-xs" : "text-sm",
            )}
          >
            {message.content}
          </p>
        ) : (
          /* Rendered markdown for AI messages */
          <div
            className={cn("prose-container", compact ? "text-xs" : "text-sm")}
          >
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={markdownComponents}
            >
              {message.content}
            </ReactMarkdown>
          </div>
        )}
      </div>
    </div>
  );
}

const MemoizedMessageBubble = memo(MessageBubble);

export default MemoizedMessageBubble;
