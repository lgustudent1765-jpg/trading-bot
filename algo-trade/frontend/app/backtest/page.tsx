import { FlaskConical } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";

export default function BacktestPage() {
  return (
    <div className="p-5 md:p-6">
      <Card>
        <CardContent className="flex flex-col items-center justify-center py-16 gap-3 text-center">
          <FlaskConical className="w-8 h-8 text-zinc-600" />
          <p className="text-sm font-medium text-zinc-400">Backtester</p>
          <p className="text-xs text-zinc-600 max-w-xs">
            Run historical simulations and review backtest results here.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
