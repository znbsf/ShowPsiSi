#pragma once
#include <QSyntaxHighlighter>
#include <QRegularExpression>
// Formatting only: XML stays plain selectable text; no HTML or resource loading.
class XmlHighlighter final : public QSyntaxHighlighter {
    bool light_=false;
public:
    void setLight(bool light){light_=light;rehighlight();}
    explicit XmlHighlighter(QTextDocument* document): QSyntaxHighlighter(document) {}
protected:
    void highlightBlock(const QString& text) override {
        struct Rule { const char* pattern; const char* color; const char* lightColor; };
        static const Rule rules[] = {
            {R"(</?[^\s<>/]+|/?>)", "#78acfa", "#155fbe"},
            {R"([A-Za-z_][\w:.-]*(?=\s*=))", "#9cdcfe", "#166677"},
            {R"("[^"\n]*"|'[^'\n]*')", "#d6a089", "#94471f"},
            {R"(&[A-Za-z0-9#]+;)", "#dcdcaa", "#806000"}
        };
        for (const auto& rule : rules) {
            auto matches = QRegularExpression(QString::fromLatin1(rule.pattern)).globalMatch(text);
            while (matches.hasNext()) { auto match=matches.next(); setFormat(match.capturedStart(),match.capturedLength(),QColor(light_?rule.lightColor:rule.color)); }
        }
        int start = previousBlockState()==1 ? 0 : text.indexOf("<!--");
        setCurrentBlockState(0);
        while(start >= 0) {
            const int end=text.indexOf("-->",start);
            if(end<0) {setFormat(start,text.size()-start,QColor(light_?"#466c31":"#a3b88c"));setCurrentBlockState(1);break;}
            setFormat(start,end+3-start,QColor(light_?"#466c31":"#a3b88c"));start=text.indexOf("<!--",end+3);
        }
    }
};
