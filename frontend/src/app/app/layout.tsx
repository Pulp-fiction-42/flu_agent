"use client";

import { AuthProvider } from "@/components/auth-provider";
import { FileContextProvider } from "@/components/file-context";
import { ConversationList } from "@/components/conversation-list";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthProvider>
      <FileContextProvider>
        <div className="flex h-screen bg-background overflow-hidden">
          <ConversationList />
          <div className="flex-1 flex flex-col min-w-0">
            {children}
          </div>
        </div>
      </FileContextProvider>
    </AuthProvider>
  );
}
