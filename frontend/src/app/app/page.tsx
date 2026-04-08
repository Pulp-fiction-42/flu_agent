"use client";

import { useRouter } from "next/navigation";
import { useState, useRef, useEffect } from "react";
import { Dna, Zap, Paperclip, Cpu, ChevronDown, X, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { getToken } from "@/lib/auth";
import { getModels, uploadFiles } from "@/lib/api";
import { useFiles } from "@/components/file-context";

const SUGGESTIONS = [
  "计算 FASTA 文件的 GC 含量",
  "对 FASTQ 进行质控分析",
  "搜索流感病毒 HA 序列",
  "构建系统发育树",
];

export default function AppPage() {
  const router = useRouter();
  const { files: uploadedFiles, addFiles, removeFile } = useFiles();
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  // Model state
  const [models, setModels] = useState<any[]>([]);
  const [selectedModel, setSelectedModel] = useState("");
  const [showModelPicker, setShowModelPicker] = useState(false);

  // File upload
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isUploading, setIsUploading] = useState(false);

  // Load available models on mount
  useEffect(() => {
    getModels()
      .then((m) => {
        setModels(m);
        if (m.length > 0) setSelectedModel(m[0].id);
      })
      .catch((e) => console.error("Failed to load models", e));
  }, []);

  // Close model picker when clicking outside
  useEffect(() => {
    if (!showModelPicker) return;
    const handler = () => setShowModelPicker(false);
    document.addEventListener("click", handler);
    return () => document.removeEventListener("click", handler);
  }, [showModelPicker]);

  const selectedModelName =
    models.find((m) => m.id === selectedModel)?.name ?? selectedModel;

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files?.length) return;
    setIsUploading(true);
    try {
      const response = await uploadFiles(Array.from(e.target.files));
      if (response.files) addFiles(response.files);
    } catch {
      alert("上传失败，请确认已登录并重试。");
    } finally {
      setIsUploading(false);
      e.target.value = "";
    }
  };

  const startNewConversation = async (msg: string) => {
    if (!msg.trim() || isLoading) return;
    setIsLoading(true);
    try {
      const token = getToken();
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api"}/conversations`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify({
            title: msg.slice(0, 20) + (msg.length > 20 ? "..." : ""),
          }),
        }
      );
      const conv = await res.json();
      // Pass initial message and selected model as query params
      const params = new URLSearchParams();
      params.set("init", msg);
      if (selectedModel) params.set("model", selectedModel);
      router.push(`/app/${conv.id}?${params.toString()}`);
    } catch (e) {
      console.error(e);
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      startNewConversation(input);
    }
  };

  return (
    <div className="flex-1 flex flex-col items-center justify-center min-h-screen px-6 pb-16 bg-background">
      {/* Hero */}
      <div className="flex flex-col items-center text-center space-y-4 mb-10">
        <div className="p-4 bg-primary/10 rounded-2xl mb-2">
          <Dna className="w-12 h-12 text-primary" />
        </div>
        <h1 className="text-4xl font-bold tracking-tight">
          What can I help you analyze?
        </h1>
        <p className="text-muted-foreground text-lg max-w-md">
          Your AI-powered bioinformatics assistant. Upload sequences, run QC
          pipelines, or explore phylogenetics.
        </p>
      </div>

      {/* Input Card */}
      <div className="w-full max-w-2xl">
        {/* Uploaded files strip */}
        {uploadedFiles.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mb-2 px-1">
            {uploadedFiles.map((f) => (
              <span
                key={f.path}
                className="flex items-center gap-1 text-[11px] px-2.5 py-1 bg-primary/10 text-primary rounded-full border border-primary/20"
              >
                📎 {f.filename}
                <button
                  onClick={() => removeFile(f.path)}
                  className="ml-0.5 hover:text-destructive"
                >
                  <X className="w-2.5 h-2.5" />
                </button>
              </span>
            ))}
          </div>
        )}

        <div className="relative group">
          <div className="absolute inset-0 bg-primary/5 blur-2xl rounded-full opacity-0 group-focus-within:opacity-100 transition-opacity" />
          <div className="relative bg-background border-2 rounded-3xl shadow-lg group-focus-within:border-primary/60 transition-all overflow-hidden">
            {/* Textarea */}
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask BioAgent commands or start analysis..."
              rows={2}
              className="w-full bg-transparent resize-none border-none outline-none text-sm px-5 pt-4 pb-2 placeholder:text-muted-foreground"
            />

            {/* Toolbar */}
            <div className="flex items-center gap-1 px-3 pb-3">
              {/* Hidden file input */}
              <input
                ref={fileInputRef}
                type="file"
                multiple
                className="hidden"
                onChange={handleFileUpload}
              />

              {/* 📎 File upload button */}
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="h-8 w-8 text-muted-foreground hover:text-primary"
                onClick={() => fileInputRef.current?.click()}
                disabled={isUploading}
                title="上传文件"
              >
                {isUploading ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Paperclip className="w-4 h-4" />
                )}
              </Button>

              {/* 🧠 Model picker */}
              <div className="relative" onClick={(e) => e.stopPropagation()}>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="h-8 gap-1 text-xs text-muted-foreground hover:text-primary px-2"
                  onClick={() => setShowModelPicker((p) => !p)}
                >
                  <Cpu className="w-3.5 h-3.5" />
                  <span className="max-w-[120px] truncate">
                    {selectedModelName || "Model"}
                  </span>
                  <ChevronDown className="w-3 h-3" />
                </Button>

                {showModelPicker && (
                  <div className="absolute bottom-10 left-0 z-50 w-72 bg-background border rounded-xl shadow-xl p-1 max-h-60 overflow-y-auto">
                    {models.length === 0 ? (
                      <p className="text-xs text-muted-foreground px-3 py-2">
                        暂无可用模型，请检查后端连接。
                      </p>
                    ) : (
                      models.map((m) => (
                        <button
                          key={m.id}
                          className={`w-full text-left text-xs px-3 py-2 rounded-lg hover:bg-muted transition-colors ${
                            selectedModel === m.id
                              ? "bg-primary/10 text-primary font-medium"
                              : ""
                          }`}
                          onClick={() => {
                            setSelectedModel(m.id);
                            setShowModelPicker(false);
                          }}
                        >
                          {m.name}
                        </button>
                      ))
                    )}
                  </div>
                )}
              </div>

              <div className="flex-1" />

              {/* ⚡ Start button */}
              <Button
                onClick={() => startNewConversation(input)}
                disabled={!input.trim() || isLoading}
                className="rounded-2xl h-9 px-5 shrink-0"
              >
                {isLoading ? (
                  <Loader2 className="w-4 h-4 animate-spin mr-1" />
                ) : (
                  <Zap className="w-4 h-4 mr-1" />
                )}
                Start
              </Button>
            </div>
          </div>
        </div>

        {/* Suggestions */}
        <div className="grid grid-cols-2 gap-2 mt-4">
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              onClick={() => startNewConversation(s)}
              className="text-left text-sm px-4 py-3 rounded-xl border bg-muted/30 hover:bg-muted/60 hover:border-primary/40 transition-all text-muted-foreground hover:text-foreground"
            >
              {s}
            </button>
          ))}
        </div>

        <p className="mt-6 text-[10px] text-center text-muted-foreground uppercase tracking-widest font-medium opacity-40">
          Powered by BioAgent Python Core • Version 3.0
        </p>
      </div>
    </div>
  );
}
