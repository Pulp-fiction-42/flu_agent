"use client";

import React, { useState, useEffect } from 'react';
import { 
  FileUp, 
  Settings, 
  History, 
  Dna, 
  Wrench, 
  Search, 
  Trash2, 
  ChevronRight,
  Database,
  Cpu
} from 'lucide-react';
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { 
  Card, 
  CardContent, 
  CardHeader, 
  CardTitle, 
  CardDescription 
} from "@/components/ui/card";
import { 
  Select, 
  SelectContent, 
  SelectItem, 
  SelectTrigger, 
  SelectValue 
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { getModels, getTools, uploadFiles } from '@/lib/api';
import { useFiles } from './file-context';

export function Sidebar() {
  const { files: uploadedFiles, addFiles, removeFile } = useFiles();
  const [models, setModels] = useState<any[]>([]);
  const [tools, setTools] = useState<any[]>([]);
  const [uploading, setUploading] = useState(false);
  const [selectedModel, setSelectedModel] = useState("");

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [modelsData, toolsData] = await Promise.all([getModels(), getTools()]);
        setModels(modelsData);
        setTools(toolsData);
        if (modelsData.length > 0) setSelectedModel(modelsData[0].id);
      } catch (err) {
        console.error("Failed to fetch sidebar data:", err);
      }
    };
    fetchData();
  }, []);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files?.length) return;
    setUploading(true);
    try {
      const response = await uploadFiles(Array.from(e.target.files));
      if (response.files) {
        addFiles(response.files);
      }
    } catch (err) {
      console.error("Upload failed:", err);
      alert("Upload failed.");
    } finally {
      setUploading(false);
      // Reset input
      e.target.value = '';
    }
  };

  return (
    <div className="w-80 border-r bg-muted/30 flex flex-col h-screen">
      <div className="p-4 flex items-center gap-2 border-b">
        <div className="p-2 bg-primary rounded-lg">
          <Dna className="w-6 h-6 text-primary-foreground" />
        </div>
        <div>
          <h1 className="font-bold text-lg tracking-tight">BioAgent</h1>
          <p className="text-xs text-muted-foreground font-medium uppercase tracking-wider">Analysis Hub</p>
        </div>
      </div>

      <ScrollArea className="flex-1 p-4">
        <div className="space-y-6">
          {/* Model Selection */}
          <section className="space-y-3">
            <div className="flex items-center gap-2 text-sm font-semibold text-muted-foreground px-1">
              <Cpu className="w-4 h-4" />
              <span>Model Selection</span>
            </div>
            <Select value={selectedModel} onValueChange={(val) => setSelectedModel(val || "")}>
              <SelectTrigger className="w-full bg-background">
                <SelectValue placeholder="Select model" />
              </SelectTrigger>
              <SelectContent>
                {models.map((m) => (
                  <SelectItem key={m.id} value={m.id}>
                    {m.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </section>

          <Separator />

          {/* File Upload */}
          <section className="space-y-3">
             <div className="flex items-center gap-2 text-sm font-semibold text-muted-foreground px-1">
              <Database className="w-4 h-4" />
              <span>Data Management</span>
            </div>
            <div className="grid w-full items-center gap-1.5">
              <label 
                htmlFor="file-upload" 
                className="flex flex-col items-center justify-center w-full h-24 border-2 border-dashed rounded-lg cursor-pointer bg-background hover:bg-muted/50 transition-colors"
              >
                <div className="flex flex-col items-center justify-center pt-5 pb-6">
                  <FileUp className="w-8 h-8 mb-2 text-muted-foreground" />
                  <p className="text-xs text-muted-foreground">Upload FastA/FastQ</p>
                </div>
                <input 
                  id="file-upload" 
                  type="file" 
                  multiple 
                  className="hidden" 
                  onChange={handleFileUpload}
                  disabled={uploading}
                />
              </label>
              {uploading && <p className="text-[10px] text-center animate-pulse">Uploading...</p>}
            </div>

            {uploadedFiles.length > 0 && (
              <div className="space-y-2 mt-2">
                {uploadedFiles.map((file) => (
                  <div key={file.path} className="flex items-center justify-between p-2 rounded-md bg-background border text-[11px] group">
                    <div className="flex items-center gap-2 overflow-hidden">
                      <div className="w-1.5 h-1.5 rounded-full bg-primary shrink-0" />
                      <span className="truncate flex-1" title={file.filename}>{file.filename}</span>
                    </div>
                    <Button 
                      variant="ghost" 
                      size="icon" 
                      className="h-5 w-5 opacity-0 group-hover:opacity-100 transition-opacity"
                      onClick={() => removeFile(file.path)}
                    >
                      <Trash2 className="h-3 w-3 text-destructive" />
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </section>

          <Separator />

          {/* Tools Status */}
          <section className="space-y-3">
            <div className="flex items-center justify-between px-1">
              <div className="flex items-center gap-2 text-sm font-semibold text-muted-foreground">
                <Settings className="w-4 h-4" />
                <span>Agent Tools</span>
              </div>
              <Badge variant="secondary" className="text-[10px]">{tools.length}</Badge>
            </div>
            <div className="space-y-1">
              {tools.slice(0, 8).map((t) => (
                <div key={t.name} className="group flex items-center justify-between p-2 rounded-md hover:bg-muted transition-colors">
                  <span className="text-xs font-medium truncate max-w-[140px]">{t.name}</span>
                  <div className="w-2 h-2 rounded-full bg-emerald-500" />
                </div>
              ))}
              {tools.length > 8 && (
                <Button variant="ghost" size="sm" className="w-full text-[10px] h-8">
                  View all tools ({tools.length})
                </Button>
              )}
            </div>
          </section>
        </div>
      </ScrollArea>

      <div className="p-4 border-t bg-muted/50">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-primary to-blue-400" />
          <div>
            <p className="text-xs font-bold leading-none">Guest User</p>
            <p className="text-[10px] text-muted-foreground mt-1">Local Session</p>
          </div>
        </div>
      </div>
    </div>
  );
}
