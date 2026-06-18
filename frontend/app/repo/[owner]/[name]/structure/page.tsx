"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { FunctionSquare, Package, Route, Database } from "lucide-react";
import { cn } from "@/lib/utils";

import FunctionsTab from "@/components/structure/FunctionsTab";
import DepsTab      from "@/components/structure/DepsTab";
import RoutesTab    from "@/components/structure/RoutesTab";
import SchemaTab    from "@/components/structure/SchemaTab";

const TABS = [
  { id: "functions",    label: "Functions",    icon: FunctionSquare },
  { id: "dependencies", label: "Dependencies", icon: Package },
  { id: "routes",       label: "API Routes",   icon: Route },
  { id: "schema",       label: "DB Schema",    icon: Database },
];

export default function StructurePage() {
  const { owner, name } = useParams<{ owner: string; name: string }>();
  const [activeTab, setActiveTab] = useState("functions");

  return (
    <div className="max-w-6xl mx-auto px-5 py-6">
      <h2 className="text-lg font-semibold text-white/80 mb-5">
        Code Structure
      </h2>

      {/* Tab switcher */}
      <div className="flex gap-1 mb-6 border-b border-white/8">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={cn(
              "flex items-center gap-1.5 px-4 py-2.5 text-sm border-b-2 transition-all",
              activeTab === tab.id
                ? "border-violet-500 text-violet-300"
                : "border-transparent text-white/40 hover:text-white/60",
            )}
          >
            <tab.icon className="w-3.5 h-3.5" />
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === "functions"    && <FunctionsTab owner={owner} name={name} />}
      {activeTab === "dependencies" && <DepsTab      owner={owner} name={name} />}
      {activeTab === "routes"       && <RoutesTab    owner={owner} name={name} />}
      {activeTab === "schema"       && <SchemaTab    owner={owner} name={name} />}
    </div>
  );
}