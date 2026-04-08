"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useRouter, usePathname } from "next/navigation";
import {
  Plus, Trash2, MessageSquare, Dna, Search, X, ChevronLeft, ChevronRight,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { listConversations, deleteConversation, ConversationSummary } from "@/lib/api";
import { useAuth } from "./auth-provider";

function formatDate(iso: string) {
  const d = new Date(iso);
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffDays = Math.floor(diffMs / 86400000);
  if (diffDays === 0) return d.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
  if (diffDays === 1) return "昨天";
  if (diffDays < 7) return `${diffDays}天前`;
  return d.toLocaleDateString("zh-CN", { month: "short", day: "numeric" });
}

export function ConversationList() {
  const router = useRouter();
  const pathname = usePathname();
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [search, setSearch] = useState("");
  const [collapsed, setCollapsed] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  // confirmId: which row is showing the inline "are you sure?" confirmation bar
  const [confirmId, setConfirmId] = useState<string | null>(null);

  const { isLoading: authLoading } = useAuth();
  const currentId = pathname?.split("/app/")?.[1];

  const fetchConversations = useCallback(async () => {
    try {
      const data = await listConversations();
      setConversations(data);
    } catch (e) {
      console.error("Failed to load conversations", e);
    }
  }, []);

  useEffect(() => {
    if (authLoading) return;
    fetchConversations();
    const interval = setInterval(fetchConversations, 5000);
    return () => clearInterval(interval);
  }, [fetchConversations, authLoading]);

  // Step 1: user clicks trash → show inline confirm bar (no window.confirm)
  const requestDelete = (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    e.preventDefault();
    setConfirmId(id);
  };

  const cancelDelete = (e: React.MouseEvent) => {
    e.stopPropagation();
    e.preventDefault();
    setConfirmId(null);
  };

  // Step 2: user clicks "删除" inside the confirm bar → actually delete
  const confirmDelete = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    e.preventDefault();
    setConfirmId(null);
    setDeletingId(id);
    try {
      await deleteConversation(id);
      setConversations((prev) => prev.filter((c) => c.id !== id));
      if (currentId === id) {
        router.push("/app");
      }
    } finally {
      setDeletingId(null);
    }
  };

  const filtered = conversations.filter((c) =>
    c.title.toLowerCase().includes(search.toLowerCase())
  );

  if (collapsed) {
    return (
      <div className="w-14 border-r bg-muted/20 flex flex-col items-center py-4 gap-3 h-screen">
        <div className="p-2 bg-primary rounded-xl mb-1">
          <Dna className="w-5 h-5 text-primary-foreground" />
        </div>
        <Button
          variant="ghost"
          size="icon"
          className="w-9 h-9"
          onClick={() => router.push("/app")}
          title="New Chat"
        >
          <Plus className="w-4 h-4" />
        </Button>
        <div className="flex-1" />
        <Button
          variant="ghost"
          size="icon"
          className="w-9 h-9"
          onClick={() => setCollapsed(false)}
          title="Expand"
        >
          <ChevronRight className="w-4 h-4" />
        </Button>
      </div>
    );
  }

  return (
    <div className="w-72 border-r bg-muted/10 flex flex-col h-screen shrink-0">
      {/* Header */}
      <div className="p-4 border-b flex items-center gap-3">
        <div className="p-1.5 bg-primary rounded-lg shrink-0">
          <Dna className="w-5 h-5 text-primary-foreground" />
        </div>
        <span className="font-bold text-base flex-1">BioAgent</span>
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8 shrink-0"
          onClick={() => setCollapsed(true)}
          title="Collapse"
        >
          <ChevronLeft className="w-4 h-4" />
        </Button>
      </div>

      {/* New Chat */}
      <div className="px-3 pt-3 pb-1">
        <Button
          variant="outline"
          className="w-full justify-start gap-2 h-9 text-sm"
          onClick={() => router.push("/app")}
        >
          <Plus className="w-4 h-4" />
          New chat
        </Button>
      </div>

      {/* Search */}
      <div className="px-3 py-2">
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-muted/50 border">
          <Search className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="搜索对话..."
            className="flex-1 bg-transparent text-xs outline-none placeholder:text-muted-foreground"
          />
          {search && (
            <button onClick={() => setSearch("")} className="shrink-0">
              <X className="w-3 h-3 text-muted-foreground hover:text-foreground" />
            </button>
          )}
        </div>
      </div>

      {/* Section label */}
      <div className="px-2 pb-1">
        <p className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground px-2 py-1">
          Chats
        </p>
      </div>

      {/* Conversation list */}
      <ScrollArea className="flex-1 px-2">
        <div className="space-y-0.5 pb-4">
          {filtered.length === 0 && (
            <p className="text-xs text-muted-foreground text-center py-8 px-4">
              {search ? "没有找到匹配的对话" : "还没有对话记录"}
            </p>
          )}

          {filtered.map((conv) => {
            const isActive = currentId === conv.id;
            const isConfirming = confirmId === conv.id;
            const isBeingDeleted = deletingId === conv.id;

            return (
              <div key={conv.id} className="w-full">
                {/* ── Inline confirmation bar (replaces window.confirm) ── */}
                {isConfirming && (
                  <div className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-destructive/10 border border-destructive/30 text-xs text-destructive">
                    <span className="flex-1 font-medium truncate">确认删除对话？</span>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-6 px-2 text-xs text-muted-foreground hover:text-foreground shrink-0"
                      onClick={cancelDelete}
                    >
                      取消
                    </Button>
                    <Button
                      size="sm"
                      className="h-6 px-2 text-xs bg-destructive hover:bg-destructive/90 text-white shrink-0"
                      onClick={(e) => confirmDelete(e, conv.id)}
                    >
                      <Trash2 className="w-3 h-3 mr-1" />
                      删除
                    </Button>
                  </div>
                )}

                {/* ── Normal conversation row ── */}
                {!isConfirming && (
                  <div
                    role="button"
                    tabIndex={0}
                    onClick={() => router.push(`/app/${conv.id}`)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        router.push(`/app/${conv.id}`);
                      }
                    }}
                    className={`w-full text-left group flex items-center gap-2 px-3 py-2.5 rounded-xl transition-all cursor-pointer ${
                      isActive
                        ? "bg-primary/10 text-foreground"
                        : "hover:bg-muted/60 text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    <MessageSquare
                      className={`w-4 h-4 shrink-0 ${isActive ? "text-primary" : ""}`}
                    />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate leading-tight">{conv.title}</p>
                      <p className="text-[10px] mt-0.5 opacity-60">{formatDate(conv.updated_at)}</p>
                    </div>
                    <Button
                      variant="ghost"
                      size="icon"
                      className={`h-6 w-6 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity ${
                        isBeingDeleted ? "opacity-100" : ""
                      }`}
                      onClick={(e) => requestDelete(e, conv.id)}
                      disabled={isBeingDeleted}
                    >
                      {isBeingDeleted ? (
                        <span className="w-3 h-3 border-2 border-destructive border-t-transparent rounded-full animate-spin inline-block" />
                      ) : (
                        <Trash2 className="w-3 h-3 text-destructive" />
                      )}
                    </Button>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </ScrollArea>

      {/* Footer */}
      <div className="p-3 border-t">
        <div className="flex items-center gap-2 px-2">
          <div className="w-7 h-7 rounded-full bg-gradient-to-tr from-primary to-blue-400 shrink-0" />
          <div className="min-w-0">
            <p className="text-xs font-semibold truncate">Guest User</p>
            <p className="text-[10px] text-muted-foreground">Local Session</p>
          </div>
        </div>
      </div>
    </div>
  );
}
