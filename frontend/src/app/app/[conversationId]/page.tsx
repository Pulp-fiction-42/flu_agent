"use client";

import { use } from "react";
import { ChatPanel } from "@/components/chat-panel";

export default function ConversationPage({
  params,
  searchParams,
}: {
  params: Promise<{ conversationId: string }>;
  searchParams: Promise<{ init?: string; model?: string }>;
}) {
  const { conversationId } = use(params);
  const { init, model } = use(searchParams);

  return (
    <ChatPanel
      conversationId={conversationId}
      initialMessage={init}
      initialModel={model}
    />
  );
}
