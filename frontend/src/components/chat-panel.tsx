"use client";

import React, { useState, useRef, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { getToken } from "@/lib/auth";
import { useFiles } from "./file-context";
import { getConversation, getModels, getTools, uploadFiles } from "@/lib/api";
import {
  Send, User, Bot, Loader2, Download, Copy, RotateCcw, Sparkles,
  Paperclip, Cpu, Wrench, X, ChevronDown,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface Message {
  role: "user" | "assistant";
  content: string;
  status?: "loading" | "done" | "error";
  files?: string[];
}

interface ChatPanelProps {
  conversationId: string;
  initialMessage?: string;
  initialModel?: string;
}

export function ChatPanel({ conversationId, initialMessage, initialModel }: ChatPanelProps) {
  const router = useRouter();
  const { files: uploadedFiles, addFiles, removeFile } = useFiles();

  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingHistory, setIsLoadingHistory] = useState(true);

  // Toolbar state
  const [models, setModels] = useState<any[]>([]);
  const [selectedModel, setSelectedModel] = useState("");
  const [tools, setTools] = useState<any[]>([]);
  const [showTools, setShowTools] = useState(false);
  const [showModelPicker, setShowModelPicker] = useState(false);

  const scrollRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const initialMessageSent = useRef(false);

  // Auto-scroll
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  // Load models and tools
  useEffect(() => {
    const fetchMeta = async () => {
      try {
        const [m, t] = await Promise.all([getModels(), getTools()]);
        setModels(m);
        // Use model from props (passed from start page) if available, otherwise first model
        if (initialModel) {
          setSelectedModel(initialModel);
        } else if (m.length > 0) {
          setSelectedModel(m[0].id);
        }
        setTools(t);
      } catch (e) {
        console.error("Failed to load models/tools", e);
      }
    };
    fetchMeta();
  }, [initialModel]);

  // Load conversation history
  useEffect(() => {
    const loadHistory = async () => {
      setIsLoadingHistory(true);
      try {
        const conv = await getConversation(conversationId);
        const hist: Message[] = conv.messages.map((m) => ({
          role: m.role,
          content: m.content,
          status: "done",
          files: m.files,
        }));
        setMessages(hist);
      } catch (e) {
        console.error("Failed to load conversation history", e);
      } finally {
        setIsLoadingHistory(false);
      }
    };
    loadHistory();
  }, [conversationId]);

  // Send initial message (from welcome page query param)
  useEffect(() => {
    if (!isLoadingHistory && initialMessage && !initialMessageSent.current) {
      initialMessageSent.current = true;
      sendMessage(initialMessage);
    }
  }, [isLoadingHistory, initialMessage]);

  const sendMessage = useCallback(async (text: string) => {
    if (!text.trim() || isLoading) return;

    const userMsg: Message = {
      role: "user",
      content: text,
      status: "done",
      files: uploadedFiles.map((f) => f.path),
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setIsLoading(true);

    const assistantMsg: Message = { role: "assistant", content: "", status: "loading" };
    setMessages((prev) => [...prev, assistantMsg]);

    try {
      const token = getToken();
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api"}/chat`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify({
            message: text,
            conversation_id: conversationId,
            model: selectedModel || undefined,
            files: uploadedFiles.map((f) => f.path),
          }),
        }
      );

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const data = await response.json();
      const result = data.result ?? JSON.stringify(data);

      setMessages((prev) => {
        const updated = [...prev];
        updated[updated.length - 1] = {
          role: "assistant",
          content: result,
          status: "done",
        };
        return updated;
      });
    } catch (err) {
      console.error("Chat error:", err);
      setMessages((prev) => {
        const updated = [...prev];
        updated[updated.length - 1] = {
          role: "assistant",
          content: "Error: Failed to connect to BioAgent.",
          status: "error",
        };
        return updated;
      });
    } finally {
      setIsLoading(false);
    }
  }, [conversationId, isLoading, selectedModel, uploadedFiles]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    sendMessage(input);
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files?.length) return;
    try {
      const response = await uploadFiles(Array.from(e.target.files));
      if (response.files) addFiles(response.files);
    } catch {
      alert("Upload failed.");
    } finally {
      e.target.value = "";
    }
  };

  const copyToClipboard = async (text: string) => {
    await navigator.clipboard.writeText(text).catch(console.error);
  };

  const selectedModelName = models.find((m) => m.id === selectedModel)?.name ?? selectedModel;

  return (
    <div className="flex-1 flex flex-col h-screen bg-background relative">
      {/* Header */}
      <div className="h-14 border-b flex items-center justify-between px-6 bg-background/50 backdrop-blur-sm z-10 shrink-0">
        <div className="flex items-center gap-2">
          <Badge variant="outline" className="bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950 dark:text-emerald-400">
            <span className="w-2 h-2 rounded-full bg-emerald-500 mr-2 animate-pulse" />
            Online
          </Badge>
          <Separator orientation="vertical" className="h-4 mx-2" />
          <span className="text-xs text-muted-foreground font-mono truncate max-w-[200px]">
            {conversationId}
          </span>
        </div>
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8"
          onClick={() => router.push("/app")}
          title="New Chat"
        >
          <RotateCcw className="h-4 w-4" />
        </Button>
      </div>

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-6 min-h-0">
        <div className="max-w-3xl mx-auto space-y-8">
          {isLoadingHistory && (
            <div className="flex justify-center pt-20">
              <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
            </div>
          )}

          {!isLoadingHistory && messages.length === 0 && !initialMessage && (
            <div className="flex flex-col items-center justify-center pt-20 text-center space-y-4">
              <div className="p-4 bg-primary/10 rounded-full">
                <Sparkles className="w-12 h-12 text-primary" />
              </div>
              <h2 className="text-2xl font-bold tracking-tight">Ready to analyze</h2>
              <p className="text-muted-foreground max-w-sm">
                Upload sequences or ask BioAgent anything about bioinformatics.
              </p>
            </div>
          )}

          {messages.map((m, i) => (
            <div key={i} className={`flex gap-4 ${m.role === "user" ? "justify-end" : "justify-start"}`}>
              {m.role === "assistant" && (
                <Avatar className="h-8 w-8 border bg-primary/5 shrink-0">
                  <AvatarFallback className="text-primary">
                    <Bot size={18} />
                  </AvatarFallback>
                </Avatar>
              )}

              <div className={`flex flex-col gap-2 max-w-[85%] ${m.role === "user" ? "items-end" : "items-start"}`}>
                {/* Files badge */}
                {m.files && m.files.length > 0 && (
                  <div className="flex flex-wrap gap-1">
                    {m.files.map((f) => (
                      <span key={f} className="text-[10px] px-2 py-0.5 bg-primary/10 text-primary rounded-full">
                        📎 {f.split("/").pop()}
                      </span>
                    ))}
                  </div>
                )}

                <div
                  className={`p-4 rounded-2xl text-sm leading-relaxed shadow-sm ${
                    m.role === "user"
                      ? "bg-primary text-primary-foreground rounded-tr-none"
                      : "bg-muted border rounded-tl-none"
                  }`}
                >
                  <div className="prose prose-sm dark:prose-invert max-w-none break-words">
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm]}
                      components={{
                        p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
                        ul: ({ children }) => <ul className="list-disc pl-4 mb-2">{children}</ul>,
                        ol: ({ children }) => <ol className="list-decimal pl-4 mb-2">{children}</ol>,
                        code: ({ ...props }) => <code className="bg-muted-foreground/20 rounded px-1 py-0.5 font-mono text-[13px]" {...props} />,
                        pre: ({ children }) => <pre className="bg-muted-foreground/10 rounded-lg p-3 my-2 overflow-x-auto border">{children}</pre>,
                        table: ({ children }) => <div className="overflow-x-auto my-2"><table className="border-collapse border border-muted-foreground/30 w-full text-xs">{children}</table></div>,
                        th: ({ children }) => <th className="border border-muted-foreground/30 px-2 py-1 bg-muted-foreground/10">{children}</th>,
                        td: ({ children }) => <td className="border border-muted-foreground/30 px-2 py-1">{children}</td>,
                      }}
                    >
                      {m.content}
                    </ReactMarkdown>
                  </div>
                  {m.status === "loading" && (
                    <span className="inline-block w-1 h-4 bg-primary/40 animate-pulse ml-1 align-middle" />
                  )}
                </div>

                <div className="flex items-center gap-3 px-1">
                  <p className="text-[10px] text-muted-foreground font-medium uppercase tracking-tighter">
                    {m.role === "user" ? "Scientist" : "BioAgent Intelligence"}
                  </p>
                  {m.role === "assistant" && m.status === "done" && (
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-5 w-5 text-muted-foreground hover:text-primary"
                      onClick={() => copyToClipboard(m.content)}
                    >
                      <Copy size={11} />
                    </Button>
                  )}
                </div>
              </div>

              {m.role === "user" && (
                <Avatar className="h-8 w-8 border bg-muted shrink-0">
                  <AvatarFallback><User size={18} /></AvatarFallback>
                </Avatar>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Input area */}
      <div className="px-4 pb-4 bg-gradient-to-t from-background via-background to-transparent shrink-0">
        <div className="max-w-3xl mx-auto">

          {/* Uploaded files strip */}
          {uploadedFiles.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mb-2 px-1">
              {uploadedFiles.map((f) => (
                <span
                  key={f.path}
                  className="flex items-center gap-1 text-[11px] px-2.5 py-1 bg-primary/10 text-primary rounded-full border border-primary/20"
                >
                  📎 {f.filename}
                  <button onClick={() => removeFile(f.path)} className="ml-0.5 hover:text-destructive">
                    <X className="w-2.5 h-2.5" />
                  </button>
                </span>
              ))}
            </div>
          )}

          <form onSubmit={handleSubmit} className="relative group">
            <div className="absolute inset-0 bg-primary/5 blur-xl rounded-full opacity-0 group-focus-within:opacity-100 transition-opacity" />
            <div className="relative bg-background border-2 rounded-3xl shadow-lg group-focus-within:border-primary/50 transition-all overflow-hidden">
              {/* Textarea */}
              <textarea
                ref={textareaRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    handleSubmit(e);
                  }
                }}
                placeholder="Ask BioAgent commands or start analysis..."
                rows={2}
                className="w-full bg-transparent resize-none border-none outline-none text-sm px-5 pt-4 pb-2 placeholder:text-muted-foreground"
              />

              {/* Toolbar */}
              <div className="flex items-center gap-1 px-3 pb-3">
                {/* File upload */}
                <input
                  ref={fileInputRef}
                  type="file"
                  multiple
                  className="hidden"
                  onChange={handleFileUpload}
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 text-muted-foreground hover:text-primary"
                  onClick={() => fileInputRef.current?.click()}
                  title="Upload file"
                >
                  <Paperclip className="w-4 h-4" />
                </Button>

                {/* Model picker */}
                <div className="relative">
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="h-8 gap-1 text-xs text-muted-foreground hover:text-primary px-2"
                    onClick={() => { setShowModelPicker((p) => !p); setShowTools(false); }}
                  >
                    <Cpu className="w-3.5 h-3.5" />
                    <span className="max-w-[100px] truncate">{selectedModelName || "Model"}</span>
                    <ChevronDown className="w-3 h-3" />
                  </Button>
                  {showModelPicker && (
                    <div className="absolute bottom-10 left-0 z-50 w-64 bg-background border rounded-xl shadow-xl p-1 max-h-60 overflow-y-auto">
                      {models.map((m) => (
                        <button
                          key={m.id}
                          className={`w-full text-left text-xs px-3 py-2 rounded-lg hover:bg-muted transition-colors ${selectedModel === m.id ? "bg-primary/10 text-primary font-medium" : ""}`}
                          onClick={() => { setSelectedModel(m.id); setShowModelPicker(false); }}
                        >
                          {m.name}
                        </button>
                      ))}
                    </div>
                  )}
                </div>

                {/* Tools panel */}
                <div className="relative">
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="h-8 gap-1 text-xs text-muted-foreground hover:text-primary px-2"
                    onClick={() => { setShowTools((p) => !p); setShowModelPicker(false); }}
                  >
                    <Wrench className="w-3.5 h-3.5" />
                    <span>Tools ({tools.length})</span>
                  </Button>
                  {showTools && (
                    <div className="absolute bottom-10 left-0 z-50 w-64 bg-background border rounded-xl shadow-xl p-3 max-h-72 overflow-y-auto">
                      <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-2">Agent Tools</p>
                      <div className="space-y-0.5">
                        {tools.map((t) => (
                          <div key={t.name} className="flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-muted">
                            <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 shrink-0" />
                            <span className="text-xs font-medium">{t.name}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>

                <div className="flex-1" />

                {/* Send button */}
                <Button
                  type="submit"
                  size="icon"
                  className="rounded-full h-9 w-9 shrink-0 transition-transform hover:scale-105 active:scale-95"
                  disabled={isLoading || !input.trim()}
                >
                  {isLoading ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Send className="h-4 w-4" />
                  )}
                </Button>
              </div>
            </div>
          </form>

          <p className="mt-2 text-[10px] text-center text-muted-foreground uppercase tracking-widest font-medium opacity-40">
            Powered by BioAgent Python Core • Version 3.0
          </p>
        </div>
      </div>
    </div>
  );
}
