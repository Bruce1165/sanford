import { useState, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';

// ─── 纯工具函数（移到组件外部，避免 TDZ 问题）─────────────────────────────
function parseDate(dateStr: string): Date | null {
  if (!dateStr || !/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) return null;
  const [year, month, day] = dateStr.split('-').map(Number);
  return new Date(year, month - 1, day);
}

function formatDate(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

// ─────────────────────────────────────────────────────────────────────────────

interface CalendarPickerProps {
  value: string;
  onChange: (date: string) => void;
  onClose: () => void;
  anchorRef: React.RefObject<HTMLElement | null>;
  minDate?: string;
  maxDate?: string;
}

function CalendarPicker({ value, onChange, onClose, anchorRef, minDate, maxDate }: CalendarPickerProps) {
  // parseDate/formatDate 现在在组件外部定义，调用时不再触发 TDZ
  const [currentMonth, setCurrentMonth] = useState(() => {
    const parsed = parseDate(value);
    return parsed || new Date();
  });
  const popupRef = useRef<HTMLDivElement>(null);
  const [position, setPosition] = useState({ top: 0, left: 0 });

  useEffect(() => {
    if (anchorRef.current) {
      const rect = anchorRef.current.getBoundingClientRect();
      // position:fixed — coords are viewport-relative, no scrollX/Y needed
      const popupWidth = 280;
      const popupHeight = 300; // estimated height
      // Flip up if not enough space below
      const spaceBelow = window.innerHeight - rect.bottom;
      const top = spaceBelow > popupHeight
        ? rect.bottom + 4
        : rect.top - popupHeight - 4;
      const left = Math.max(8, Math.min(rect.left, window.innerWidth - popupWidth - 8));
      setPosition({ top, left });
    }
  }, [anchorRef]);

  useEffect(() => {
    // Use setTimeout so the listener is added AFTER the current click event
    // finishes propagating, preventing immediate self-close on open
    const timer = setTimeout(() => {
      const handleClickOutside = (event: MouseEvent) => {
        if (popupRef.current && !popupRef.current.contains(event.target as Node)) {
          onClose();
        }
      };
      document.addEventListener('mousedown', handleClickOutside);
      // Store cleanup on the ref so we can remove it
      (popupRef as any)._cleanup = () => document.removeEventListener('mousedown', handleClickOutside);
    }, 0);
    return () => {
      clearTimeout(timer);
      if ((popupRef as any)._cleanup) (popupRef as any)._cleanup();
    };
  }, [onClose]);

  const generateDays = () => {
    const year = currentMonth.getFullYear();
    const month = currentMonth.getMonth();
    const firstDay = new Date(year, month, 1);
    const lastDay = new Date(year, month + 1, 0);
    const daysInMonth = lastDay.getDate();
    const startingDay = firstDay.getDay();

    const days: (number | null)[] = [];
    for (let i = 0; i < startingDay; i++) days.push(null);
    for (let i = 1; i <= daysInMonth; i++) days.push(i);
    return days;
  };

  const handleDayClick = (day: number) => {
    const year = currentMonth.getFullYear();
    const month = currentMonth.getMonth();
    const date = new Date(year, month, day);
    const dateStr = formatDate(date);
    if (minDate && dateStr < minDate) return;
    if (maxDate && dateStr > maxDate) return;
    onChange(dateStr);
    onClose();
  };

  const navigateMonth = (direction: number) => {
    setCurrentMonth(new Date(currentMonth.getFullYear(), currentMonth.getMonth() + direction, 1));
  };

  const goToToday = () => {
    const today = new Date();
    onChange(formatDate(today));
    onClose();
  };

  const days = generateDays();
  const selectedDate = parseDate(value);
  const today = new Date();
  const todayStr = formatDate(today);

  const weekDays = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
  const monthNames = ['January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'];

  const popup = (
    <div
      ref={popupRef}
      className="calendar-popup"
      style={{ top: `${position.top}px`, left: `${position.left}px` }}
    >
      <div className="calendar-header">
        <button onClick={() => navigateMonth(-1)} type="button">‹</button>
        <span className="calendar-month-year">
          {monthNames[currentMonth.getMonth()]} {currentMonth.getFullYear()}
        </span>
        <button onClick={() => navigateMonth(1)} type="button">›</button>
      </div>

      <div className="calendar-grid">
        {weekDays.map(day => (
          <div key={day} className="calendar-day-header">{day}</div>
        ))}
        {days.map((day, index) => {
          if (day === null) {
            return <div key={`empty-${index}`} className="calendar-day blank" />;
          }
          const year = currentMonth.getFullYear();
          const month = currentMonth.getMonth();
          const dateStr = formatDate(new Date(year, month, day));
          const isSelected = selectedDate &&
            selectedDate.getDate() === day &&
            selectedDate.getMonth() === month &&
            selectedDate.getFullYear() === year;
          const isToday = dateStr === todayStr;
          const isDisabled = !!(minDate && dateStr < minDate) || !!(maxDate && dateStr > maxDate);

          return (
            <button
              key={day}
              className={`calendar-day ${isSelected ? 'selected' : ''} ${isToday ? 'today' : ''} ${isDisabled ? 'disabled' : ''}`}
              onClick={() => !isDisabled && handleDayClick(day)}
              disabled={isDisabled}
              type="button"
            >
              {day}
            </button>
          );
        })}
      </div>

      <div className="calendar-footer">
        <button onClick={goToToday} type="button" className="today-btn">
          Today
        </button>
      </div>
    </div>
  );
  return createPortal(popup, document.body);
}

interface DateInputProps {
  value: string;
  onChange: (date: string) => void;
  inputRef?: React.RefObject<HTMLInputElement | null>;
}

function DateInput({ value, onChange, inputRef }: DateInputProps) {
  return (
    <input
      ref={inputRef}
      type="text"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder="YYYY-MM-DD"
      className="wsj-input"
      style={{ width: '120px' }}
      autoComplete="off"
      autoCorrect="off"
      autoCapitalize="off"
      spellCheck={false}
    />
  );
}

interface CalendarProps {
  value: string;
  onChange: (date: string) => void;
  minDate?: string;
  maxDate?: string;
}

export function Calendar({ value, onChange, minDate, maxDate }: CalendarProps) {
  const [isOpen, setIsOpen] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  return (
    <>
      <DateInput value={value} onChange={onChange} inputRef={inputRef} />
      {isOpen && inputRef.current && (
        <CalendarPicker
          value={value}
          onChange={onChange}
          onClose={() => setIsOpen(false)}
          anchorRef={inputRef}
          minDate={minDate}
          maxDate={maxDate}
        />
      )}
    </>
  );
}

interface CalendarButtonProps {
  onClick: () => void;
}

export function CalendarButton({ onClick }: CalendarButtonProps) {
  return (
    <button
      className="calendar-toggle"
      onClick={onClick}
      type="button"
      aria-label="Open calendar"
    >
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect>
        <line x1="16" y1="2" x2="16" y2="6"></line>
        <line x1="8" y1="2" x2="8" y2="6"></line>
        <line x1="3" y1="10" x2="21" y2="10"></line>
      </svg>
    </button>
  );
}

// Combined component with external button
interface CalendarWithButtonProps extends CalendarProps {
  showPicker: boolean;
  onTogglePicker: () => void;
  onSelectDate: (date: string) => void;
}

export function CalendarWithButton({
  value,
  onChange,
  minDate,
  maxDate,
  showPicker,
  onTogglePicker,
  onSelectDate,
}: CalendarWithButtonProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  // refReady removed — DateInput is always rendered so inputRef is always set
  // by the time CalendarPicker's useEffect fires (React commits refs before effects)

  return (
    <>
      <DateInput value={value} onChange={onChange} inputRef={inputRef} />
      <CalendarButton onClick={onTogglePicker} />
      {showPicker && (
        <CalendarPicker
          value={value}
          onChange={onSelectDate}
          onClose={() => onTogglePicker()}
          anchorRef={inputRef}
          minDate={minDate}
          maxDate={maxDate}
        />
      )}
    </>
  );
}
