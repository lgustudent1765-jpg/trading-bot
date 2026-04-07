import { Zap } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";

export default function SignalsPage() {
  return (
    <div className="p-5 md:p-6">
      <Card>
        <CardContent className="flex flex-col items-center justify-center py-16 gap-3 text-center">
          <Zap className="w-8 h-8 text-zinc-600" />
          <p className="text-sm font-medium text-zinc-400">Signals</p>
          <p className="text-xs text-zinc-600 max-w-xs">
            Real-time strategy signals will appear here once your backend is connected.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
